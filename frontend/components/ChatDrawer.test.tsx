import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";

import { ChatDrawer } from "@/components/ChatDrawer";
import { GENERIC_RETRY_MESSAGE } from "@/hooks/useChat";

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function open() {
  fireEvent.click(screen.getByTestId("chat-toggle"));
}

describe("ChatDrawer", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  it("fetches history exactly once, only after the drawer is first opened", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, []));

    render(<ChatDrawer />);

    expect(fetchMock).not.toHaveBeenCalled();

    open(); // open
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock.mock.calls[0][0]).toBe("/api/chat/history");

    open(); // close
    open(); // reopen

    await waitFor(() => expect(screen.getByTestId("chat-quick-prompts")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("shows the loading line while the history fetch is pending, with no quick prompts or bubbles", async () => {
    let resolveFetch: (value: Response) => void = () => {};
    const pending = new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    });
    fetchMock.mockImplementation((url: string) => {
      if (url === "/api/chat/history") return pending;
      throw new Error(`unexpected fetch ${url}`);
    });

    render(<ChatDrawer />);
    open();

    expect(screen.getByTestId("chat-history-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-quick-prompts")).not.toBeInTheDocument();

    resolveFetch(jsonResponse(200, []));
    await waitFor(() => expect(screen.getByTestId("chat-quick-prompts")).toBeInTheDocument());
  });

  it("shows the framing line and exactly three quick prompts on an empty transcript", async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url === "/api/chat/history") return Promise.resolve(jsonResponse(200, []));
      throw new Error(`unexpected fetch ${url}`);
    });

    render(<ChatDrawer />);
    open();

    await waitFor(() => expect(screen.getByTestId("chat-quick-prompts")).toBeInTheDocument());
    const buttons = within(screen.getByTestId("chat-quick-prompts")).getAllByRole("button");
    expect(buttons).toHaveLength(3);
  });

  it("sends a quick prompt's exact text immediately without populating the input box", async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url === "/api/chat/history") return Promise.resolve(jsonResponse(200, []));
      if (url === "/api/chat") {
        return Promise.resolve(
          jsonResponse(200, {
            message: "Your portfolio looks fine.",
            actions: { trades: [], watchlist_changes: [] },
          }),
        );
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    render(<ChatDrawer />);
    open();
    await waitFor(() => expect(screen.getByTestId("chat-quick-prompts")).toBeInTheDocument());

    const buttons = within(screen.getByTestId("chat-quick-prompts")).getAllByRole("button");
    const firstLabel = buttons[0].textContent;
    fireEvent.click(buttons[0]);

    await waitFor(() => {
      const postCall = fetchMock.mock.calls.find(([url]) => url === "/api/chat");
      expect(postCall).toBeTruthy();
    });
    const [, postInit] = fetchMock.mock.calls.find(([url]) => url === "/api/chat")!;
    expect(JSON.parse(postInit.body as string)).toEqual({ message: firstLabel });

    expect((screen.getByTestId("chat-input") as HTMLTextAreaElement).value).toBe("");
  });

  it("removes the quick-prompt block once at least one message exists", async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url === "/api/chat/history") return Promise.resolve(jsonResponse(200, []));
      if (url === "/api/chat") {
        return Promise.resolve(
          jsonResponse(200, { message: "ok", actions: { trades: [], watchlist_changes: [] } }),
        );
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    render(<ChatDrawer />);
    open();
    await waitFor(() => expect(screen.getByTestId("chat-quick-prompts")).toBeInTheDocument());

    const buttons = within(screen.getByTestId("chat-quick-prompts")).getAllByRole("button");
    fireEvent.click(buttons[0]);

    await waitFor(() =>
      expect(screen.queryByTestId("chat-quick-prompts")).not.toBeInTheDocument(),
    );
  });

  it("restores prior turns including trade cards from history, with no quick prompts", async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url === "/api/chat/history") {
        return Promise.resolve(
          jsonResponse(200, [
            { role: "user", content: "Buy 10 AAPL", actions: null },
            {
              role: "assistant",
              content: "Buying 10 AAPL.",
              actions: {
                trades: [{ success: true, ticker: "AAPL", side: "buy", quantity: 10, price: 190 }],
                watchlist_changes: [],
              },
            },
          ]),
        );
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    render(<ChatDrawer />);
    open();

    await waitFor(() => expect(screen.getByTestId("chat-message-assistant")).toBeInTheDocument());
    expect(screen.getByTestId("trade-card")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-quick-prompts")).not.toBeInTheDocument();
  });

  it("disables Send and shows the thinking indicator while a send is in flight", async () => {
    let resolveSend: (value: Response) => void = () => {};
    const pending = new Promise<Response>((resolve) => {
      resolveSend = resolve;
    });
    fetchMock.mockImplementation((url: string) => {
      if (url === "/api/chat/history") return Promise.resolve(jsonResponse(200, []));
      if (url === "/api/chat") return pending;
      throw new Error(`unexpected fetch ${url}`);
    });

    render(<ChatDrawer />);
    open();
    await waitFor(() => expect(screen.getByTestId("chat-quick-prompts")).toBeInTheDocument());

    const input = screen.getByTestId("chat-input") as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "Hi" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    await waitFor(() => expect(screen.getByTestId("chat-send")).toBeDisabled());
    expect(screen.getByTestId("chat-thinking")).toBeInTheDocument();
    expect(screen.getByTestId("chat-send").textContent).toBe("Sending…");

    resolveSend(
      jsonResponse(200, { message: "ok", actions: { trades: [], watchlist_changes: [] } }),
    );
    // draft clears on a successful reply, so the button legitimately stays
    // disabled again (empty input) -- assert sending ended via the label
    // and the thinking indicator instead of the disabled attribute.
    await waitFor(() => expect(screen.getByTestId("chat-send").textContent).toBe("Send"));
    expect(screen.queryByTestId("chat-thinking")).not.toBeInTheDocument();
  });

  it("renders the error bubble on a rejected fetch and leaves the typed input unchanged", async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url === "/api/chat/history") return Promise.resolve(jsonResponse(200, []));
      if (url === "/api/chat") return Promise.reject(new Error("network down"));
      throw new Error(`unexpected fetch ${url}`);
    });

    render(<ChatDrawer />);
    open();
    await waitFor(() => expect(screen.getByTestId("chat-quick-prompts")).toBeInTheDocument());

    const input = screen.getByTestId("chat-input") as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "Buy 10 AAPL" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    await waitFor(() =>
      expect(screen.getByTestId("chat-message-assistant")).toHaveClass("border-down"),
    );
    expect(screen.getByTestId("chat-message-assistant").textContent).toBe(GENERIC_RETRY_MESSAGE);
    expect(input.value).toBe("Buy 10 AAPL");
  });

  it("renders the same error bubble when the backend answers 200 with the generic retry message", async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url === "/api/chat/history") return Promise.resolve(jsonResponse(200, []));
      if (url === "/api/chat") {
        return Promise.resolve(
          jsonResponse(200, {
            message: GENERIC_RETRY_MESSAGE,
            actions: { trades: [], watchlist_changes: [] },
          }),
        );
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    render(<ChatDrawer />);
    open();
    await waitFor(() => expect(screen.getByTestId("chat-quick-prompts")).toBeInTheDocument());

    const input = screen.getByTestId("chat-input") as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "Analyze my portfolio" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    await waitFor(() =>
      expect(screen.getByTestId("chat-message-assistant")).toHaveClass("border-down"),
    );
    expect(input.value).toBe("Analyze my portfolio");
  });
});
