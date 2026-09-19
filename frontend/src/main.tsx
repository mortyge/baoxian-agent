import React from "react";
import { createRoot } from "react-dom/client";
import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useLocalRuntime,
} from "@assistant-ui/react";
import type { ChatModelAdapter, ThreadMessage } from "@assistant-ui/react";
import "@assistant-ui/styles/index.css";
import "./styles.css";

const adapter: ChatModelAdapter = {
  async run({ messages }) {
    const requestMessages = messages
      .filter((message) => message.role === "user" || message.role === "assistant")
      .map((message) => ({
        role: message.role,
        content: extractText(message),
      }));
    const response = await fetch("/v1/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: requestMessages }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "审核服务暂时不可用");
    return { content: [{ type: "text", text: payload.content }] };
  },
};

function extractText(message: ThreadMessage) {
  return message.content
    .filter((part): part is { type: "text"; text: string } => part.type === "text")
    .map((part) => part.text)
    .join("\n");
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="message assistant">
      <span className="message-label">审核助手</span>
      <div className="message-body"><MessagePrimitive.Parts /></div>
    </MessagePrimitive.Root>
  );
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="message user">
      <span className="message-label">你</span>
      <div className="message-body"><MessagePrimitive.Parts /></div>
    </MessagePrimitive.Root>
  );
}

function App() {
  const runtime = useLocalRuntime(adapter);

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <main className="app-shell">
        <header className="topbar">
          <a className="brand" href="/" aria-label="理赔审核助手首页">
            <span className="brand-mark" aria-hidden="true">◈</span>
            <span>理赔审核助手</span>
          </a>
          <nav className="nav-links" aria-label="主导航">
            <a href="/">对话</a>
            <a href="/docs" target="_blank" rel="noreferrer">API 文档</a>
            <span className="status-dot"><i /> 本地服务</span>
          </nav>
        </header>
        <section className="chat-panel" aria-label="理赔审核对话">
          <ThreadPrimitive.Root className="conversation">
            <ThreadPrimitive.Viewport autoScroll turnAnchor="top">
              <ThreadPrimitive.Empty>
                <div className="empty-state">
                  <p className="eyebrow">INSURANCE OPERATIONS</p>
                  <h1>今天要审核哪个案件？</h1>
                  <span>输入案件编号，后台会运行保单、理赔和风险审核流程。</span>
                </div>
              </ThreadPrimitive.Empty>
              <ThreadPrimitive.Messages components={{ UserMessage, AssistantMessage }} />
              <ThreadPrimitive.ViewportFooter>
                <ComposerPrimitive.Root className="composer">
                  <ComposerPrimitive.Input
                    className="composer-input"
                    placeholder="输入案件编号或审核请求，例如：请审核 CL001"
                    aria-label="输入审核请求"
                    submitMode="enter"
                  />
                  <ComposerPrimitive.Send className="composer-send" aria-label="发送审核请求">↑</ComposerPrimitive.Send>
                </ComposerPrimitive.Root>
              </ThreadPrimitive.ViewportFooter>
            </ThreadPrimitive.Viewport>
          </ThreadPrimitive.Root>
        </section>
        <p className="notice">审核结果仅为决策支持建议，不会执行赔付或修改案件状态。</p>
      </main>
    </AssistantRuntimeProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
