"use client";

import { useState } from "react";
import {
  MessageCircle,
  X,
  Send,
  Bot,
} from "lucide-react";

export default function ChatBot() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Floating Button */}
      <button
        onClick={() => setOpen(!open)}
        className="fixed bottom-6 right-6 z-50 flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-r from-[#ff6c2f] to-[#ff8f57] text-white shadow-2xl transition-all duration-300 hover:scale-110 hover:shadow-orange-400/40"
      >
        {open ? <X size={26} /> : <MessageCircle size={28} />}
      </button>

      {/* Chat Window */}
      {open && (
        <div className="fixed bottom-28 right-6 z-50 flex h-[620px] w-[380px] flex-col overflow-hidden rounded-3xl border border-gray-200 bg-white shadow-[0_20px_60px_rgba(0,0,0,0.18)] animate-in fade-in slide-in-from-bottom-5 duration-300">

          {/* Header */}
          <div className="flex items-center justify-between bg-gradient-to-r from-[#ff6c2f] to-[#ff8f57] px-5 py-4 text-white">

            <div className="flex items-center gap-3">

              {/* Logo */}
              <div className="relative">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-[#ff6c2f] shadow-lg">
                  <Bot size={26} />
                </div>

                <span className="absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-white bg-green-500"></span>
              </div>

              <div>
                <h3 className="font-semibold text-lg">
                  Xerin Assistant
                </h3>

                <p className="text-xs text-orange-100">
                  Online • Usually replies instantly
                </p>
              </div>
            </div>

            <button
              onClick={() => setOpen(false)}
              className="rounded-full p-2 transition hover:bg-white/20"
            >
              <X size={18} />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 space-y-5 overflow-y-auto bg-gray-50 p-5">

            {/* Welcome Message */}
            <div className="flex items-start gap-3">

              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#ff6c2f] text-white">
                <Bot size={20} />
              </div>

              <div className="max-w-[250px] rounded-2xl rounded-tl-md bg-white p-4 shadow">

                <p className="text-sm text-gray-700">
                  👋 Hello and welcome to
                  <span className="font-semibold text-[#ff6c2f]">
                    {" "}Xerin Marketplace
                  </span>
                </p>

                <p className="mt-2 text-sm text-gray-600">
                  I'm here to help you find products, answer questions,
                  and assist you with your shopping experience.
                </p>

                <span className="mt-3 block text-xs text-gray-400">
                  Just now
                </span>

              </div>
            </div>

          </div>

          {/* Input */}
          <div className="border-t bg-white p-4">

            <div className="flex items-center gap-3 rounded-full border border-gray-300 bg-gray-50 px-4 py-2 focus-within:border-[#ff6c2f]">

              <input
                type="text"
                placeholder="Type your message..."
                className="flex-1 bg-transparent text-sm outline-none"
              />

              <button className="flex h-10 w-10 items-center justify-center rounded-full bg-[#ff6c2f] text-white transition hover:bg-[#e95d22]">
                <Send size={18} />
              </button>

            </div>

            <p className="mt-3 text-center text-[11px] text-gray-400">
              Powered by Xerin AI Assistant
            </p>

          </div>

        </div>
      )}
    </>
  );
}