"use client";

import { ChatContainer, ConversationSidebar } from "@/components/chat";

export default function ChatPage() {
  return (
    <div className="flex min-h-0 flex-1 -m-3 sm:-m-6">
      <ConversationSidebar />
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex-1 min-h-0">
          <ChatContainer />
        </div>
      </div>
    </div>
  );
}
