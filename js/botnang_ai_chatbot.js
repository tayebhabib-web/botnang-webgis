// BotnangBot live OpenAI/PostgreSQL frontend
// Natural answer rendering fix: shows bold and links nicely instead of raw ** and [link](url)

(function () {
  const API_URL =
    (window.location.port === "5000")
      ? "/chat"
      : "http://127.0.0.1:5000/chat";
  const history = [];

  function getProjectState() {
    return {
      scenario: window.currentScenario || window.selectedScenario || "unknown",
      year: window.currentYear || window.selectedYear || "unknown"
    };
  }

  function escapeHtml(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function cleanBotText(text) {
    return String(text || "")
      .replace(/\\\[/g, "")
      .replace(/\\\]/g, "")
      .replace(/\\text\{([^}]+)\}/g, "$1")
      .replace(/\\times/g, "×")
      .replace(/\\\(/g, "")
      .replace(/\\\)/g, "")
      .replace(/\*\*\s+/g, "**")
      .trim();
  }

  function renderBotAnswer(text) {
    let html = escapeHtml(cleanBotText(text));

    // Convert markdown links: [label](url)
    html = html.replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    );

    // Convert bold: **text**
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

    // Convert bullet lines
    html = html.replace(/(^|\n)-\s+/g, "$1• ");

    // Paragraph spacing
    html = html.replace(/\n{2,}/g, "</p><p>");
    html = html.replace(/\n/g, "<br>");

    return `<p>${html}</p>`;
  }

  function findBotPanel() {
    return (
      document.getElementById("botnangBotPanel") ||
      document.getElementById("botnang-bot-panel") ||
      document.querySelector(".botnang-bot-panel") ||
      document.querySelector(".botnangbot-panel") ||
      document.querySelector('[id*="botnang"][id*="Panel" i]') ||
      document.querySelector('[id*="bot"][id*="Panel" i]')
    );
  }

  function createChatUI(panel) {
    if (!panel || panel.querySelector("#botnangChatForm")) return;

    let body =
      panel.querySelector(".panel-body") ||
      panel.querySelector(".botnangbot-body") ||
      panel.querySelector(".chatbot-body") ||
      panel.querySelector(".dashboard-body") ||
      panel;

    if (body === panel) {
      const header =
        panel.querySelector(".panel-header") ||
        panel.querySelector(".botnangbot-header") ||
        panel.querySelector("header");
      panel.innerHTML = "";
      if (header) panel.appendChild(header);
      body = document.createElement("div");
      body.className = "botnang-chat-body";
      panel.appendChild(body);
    } else {
      body.innerHTML = "";
      body.classList.add("botnang-chat-body");
    }

    body.innerHTML = `
      <div class="botnang-chat-intro">
        <strong>Ask BotnangBot</strong>
        <span>Project-specific live AI assistant connected to PostgreSQL schema <b>botnang_bot</b>.</span>
      </div>

      <div id="botnangChatMessages" class="botnang-chat-messages" aria-live="polite">
        <div class="botnang-msg bot">
          <p>Hello! Ask me about Botnang population, building allocation, scenarios, age structure, migration, dashboard, methodology, or PostgreSQL/PostGIS workflow.</p>
        </div>
      </div>

      <form id="botnangChatForm" class="botnang-chat-form">
        <textarea
          id="botnangChatInput"
          class="botnang-chat-input"
          rows="2"
          placeholder="Ask a question about the Botnang WebGIS project..."
          required
        ></textarea>
        <button id="botnangChatSend" class="botnang-chat-send" type="submit">Send</button>
      </form>

      <div class="botnang-chat-hints">
        Try: “What is the source of the formula?” or “What is the baseline population in 2040?”
      </div>
    `;

    const form = body.querySelector("#botnangChatForm");
    const input = body.querySelector("#botnangChatInput");
    const messages = body.querySelector("#botnangChatMessages");
    const sendBtn = body.querySelector("#botnangChatSend");

    function addMessage(role, text) {
      const msg = document.createElement("div");
      msg.className = `botnang-msg ${role}`;
      if (role.includes("bot")) {
        msg.innerHTML = renderBotAnswer(text);
      } else {
        msg.textContent = text;
      }
      messages.appendChild(msg);
      messages.scrollTop = messages.scrollHeight;
      return msg;
    }

    form.addEventListener("submit", async function (event) {
      event.preventDefault();

      const question = input.value.trim();
      if (!question) return;

      addMessage("user", question);
      history.push({ role: "user", content: question });

      input.value = "";
      input.focus();
      sendBtn.disabled = true;
      sendBtn.textContent = "Thinking...";

      const loading = addMessage("bot loading", "BotnangBot is reading the project context...");

      try {
        const res = await fetch(API_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question,
            history: history.slice(-8),
            state: getProjectState()
          })
        });

        const rawText = await res.text();
        let data = {};
        try {
          data = rawText ? JSON.parse(rawText) : {};
        } catch (parseError) {
          data = {};
        }

        let answer =
          data.answer ||
          data.reply ||
          data.message ||
          data.error ||
          "";

        if (!answer && !res.ok) {
          answer =
            "BotnangBot backend returned an error. Please check the server.py terminal for details.";
        }

        if (!answer) {
          answer =
            "No answer was returned from BotnangBot. Please check that backend/server.py is running on http://127.0.0.1:5000.";
        }

        loading.remove();
        addMessage("bot", answer);
        history.push({ role: "assistant", content: answer });
      } catch (err) {
        loading.remove();
        addMessage(
          "bot error",
          "Connection error. Make sure backend is running with: py -3.12 server.py and open the project from http://localhost:5000/index.html"
        );
      } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = "Send";
      }
    });

    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
      }
    });
  }

  function initBotnangChat() {
    const panel = findBotPanel();
    if (panel) createChatUI(panel);
  }

  document.addEventListener("DOMContentLoaded", initBotnangChat);

  document.addEventListener("click", function (event) {
    const clicked = event.target.closest("#botnangBotBtn, #botnangbotBtn, .botnang-bot-btn, [id*='botnangBot' i], [id*='BotnangBot' i]");
    if (clicked) {
      setTimeout(initBotnangChat, 80);
      setTimeout(initBotnangChat, 300);
    }
  });

  setTimeout(initBotnangChat, 500);
  setTimeout(initBotnangChat, 1500);
})();
