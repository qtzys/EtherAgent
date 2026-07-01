/* ===========================================
   最核心 Agent v0 · 前端逻辑
   =========================================== */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ---------- 状态 ----------
const state = {
  isStreaming: false,
  currentTaskId: null,
  step: 1,
};

// ---------- 元素 ----------
const els = {
  chatScroll:   $('#chatScroll'),
  msgInput:     $('#msgInput'),
  btnSend:      $('#btnSend'),
  btnNewTask:   $('#btnNewTask'),
  btnInfo:      $('#btnInfo'),
  infoModal:    $('#infoModal'),
  infoBody:     $('#infoBody'),
  infoClose:    $('#infoClose'),
  taskList:     $('#taskList'),
  taskCount:    $('#taskCount'),
  statusText:   $('#statusText'),
  stepInfo:     $('#stepInfo'),
  welcome:      $('#welcome'),
};

// ===========================================
// 事件绑定
// ===========================================
els.btnSend.addEventListener('click', sendMessage);
els.btnNewTask.addEventListener('click', newTask);
els.btnInfo.addEventListener('click', showInfo);
els.btnClearAll = $('#btnClearAll');
els.btnClearAll.addEventListener('click', clearAllTasks);
els.infoClose.addEventListener('click', () => els.infoModal.style.display = 'none');
els.infoModal.addEventListener('click', (e) => {
  if (e.target === els.infoModal) els.infoModal.style.display = 'none';
});

els.msgInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// 自动调整输入框高度
els.msgInput.addEventListener('input', () => {
  els.msgInput.style.height = 'auto';
  els.msgInput.style.height = Math.min(els.msgInput.scrollHeight, 120) + 'px';
});

// ===========================================
// 新建任务
// ===========================================
function newTask() {
  state.currentTaskId = null;
  state.step = 1;
  els.chatScroll.innerHTML = '';
  els.welcome = document.createElement('div');
  els.welcome.className = 'welcome';
  els.welcome.innerHTML = `
    <div class="welcome-icon">🧠</div>
    <h1>新任务</h1>
    <p class="welcome-sub">在下方输入框开始对话</p>
  `;
  els.chatScroll.appendChild(els.welcome);
  els.statusText.textContent = '就绪';
  els.stepInfo.textContent = '第 1 步';
  refreshTaskList();
  els.msgInput.focus();
}

// ===========================================
// 发送消息（SSE 流式）
// ===========================================
async function sendMessage() {
  const text = els.msgInput.value.trim();
  if (!text || state.isStreaming) return;

  state.isStreaming = true;
  els.btnSend.disabled = true;
  els.msgInput.value = '';
  els.msgInput.style.height = 'auto';

  // 移除欢迎屏
  if (els.welcome && els.welcome.parentNode) {
    els.welcome.parentNode.removeChild(els.welcome);
    els.welcome = null;
  }

  // 1. 显示用户消息
  appendUserMessage(text);

  // 2. 创建 bot 消息容器
  const botMsg = appendBotMessage();
  els.statusText.textContent = '思考中...';

  // 3. 流式接收
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let answerBuf = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const dataStr = line.slice(6);
        if (!dataStr.trim()) continue;

        try {
          const event = JSON.parse(dataStr);
          handleEvent(event, botMsg);
          if (event.type === 'text_chunk') {
            answerBuf += event.text;
          }
        } catch (e) {
          console.error('解析事件失败:', e, dataStr);
        }
      }
    }

    // 流结束
    els.statusText.textContent = '就绪';
    refreshTaskList();
  } catch (e) {
    console.error('请求失败:', e);
    botMsg.appendChild(makeErrorBlock(`请求失败: ${e.message}`));
  } finally {
    state.isStreaming = false;
    els.btnSend.disabled = false;
    els.msgInput.focus();
  }
}

// ===========================================
// 事件处理
// ===========================================
function handleEvent(event, botMsg) {
  switch (event.type) {
    case 'task_start':
      state.currentTaskId = event.task_id;
      setBotHeader(botMsg, '核心Agent', 'running');
      break;

    case 'thinking':
      state.step = event.iteration;
      els.stepInfo.textContent = `第 ${event.iteration} 步思考`;
      appendThinking(botMsg, event.reasoning);
      break;

    case 'tool_call':
      appendToolCall(botMsg, event.tool, event.args);
      break;

    case 'tool_result':
      updateToolResult(botMsg, event);
      break;

    case 'text_chunk':
      appendTextChunk(botMsg, event.text);
      break;

    case 'answer':
      setBotHeader(botMsg, '核心Agent', 'completed');
      break;

    case 'file':
      appendFile(botMsg, event.path);
      break;

    case 'fail':
      setBotHeader(botMsg, '核心Agent', 'failed');
      appendError(botMsg, event.reason);
      break;

    case 'task_end':
      setBotHeader(botMsg, '核心Agent', event.status === '已完成' ? 'completed' : 'failed');
      break;
  }
}

// ===========================================
// UI 构造器
// ===========================================
function appendUserMessage(text) {
  const div = document.createElement('div');
  div.className = 'message msg-user';
  div.innerHTML = `<div class="msg-bubble"></div>`;
  div.querySelector('.msg-bubble').textContent = text;
  els.chatScroll.appendChild(div);
  scrollToBottom();
}

function appendBotMessage() {
  const div = document.createElement('div');
  div.className = 'message msg-bot';
  div.innerHTML = `
    <div class="msg-header" style="display:none">
      <span class="bot-name">核心Agent</span>
      <span class="msg-status-pill">处理中</span>
    </div>
    <div class="msg-content"></div>
  `;
  els.chatScroll.appendChild(div);
  scrollToBottom();
  return div.querySelector('.msg-content');
}

function setBotHeader(contentEl, name, statusKey) {
  const msgEl = contentEl.closest('.message');
  const header = msgEl.querySelector('.msg-header');
  const pill = header.querySelector('.msg-status-pill');
  header.style.display = 'flex';
  pill.className = `msg-status-pill ${statusKey}`;
  pill.textContent = {
    completed: '完成',
    running: '处理中',
    failed: '失败',
  }[statusKey] || statusKey;
}

function appendThinking(contentEl, reasoning) {
  const block = document.createElement('div');
  block.className = 'thinking-block';
  block.innerHTML = `
    <div class="thinking-label">💭 思考中</div>
    <div class="thinking-text"></div>
  `;
  block.querySelector('.thinking-text').textContent = reasoning || '(无)';
  contentEl.appendChild(block);
  scrollToBottom();
}

function appendToolCall(contentEl, tool, args) {
  const block = document.createElement('div');
  block.className = 'tool-call-block';
  block.dataset.tool = tool;
  block.innerHTML = `
    <div>
      <span class="tool-label">工具调用</span>
      <span class="tool-name"></span>
    </div>
    <div class="tool-args"></div>
    <div class="tool-output" style="display:none">
      <pre></pre>
    </div>
  `;
  block.querySelector('.tool-name').textContent = tool;
  block.querySelector('.tool-args').textContent = JSON.stringify(args, null, 2);
  contentEl.appendChild(block);
  scrollToBottom();
}

function updateToolResult(contentEl, result) {
  const blocks = contentEl.querySelectorAll('.tool-call-block');
  const lastBlock = blocks[blocks.length - 1];
  if (!lastBlock) return;

  const outputEl = lastBlock.querySelector('.tool-output');
  const preEl = lastBlock.querySelector('pre');
  outputEl.style.display = 'block';

  const statusClass = result.success ? 'tool-success' : 'tool-failed';
  const statusText = result.success ? '✓ 成功' : '✗ 失败';
  const statusSpan = document.createElement('div');
  statusSpan.className = statusClass;
  statusSpan.textContent = statusText;
  statusSpan.style.fontSize = '12px';
  statusSpan.style.fontWeight = '600';
  statusSpan.style.marginTop = '6px';

  preEl.textContent = JSON.stringify(result.result || result.error, null, 2);
  outputEl.appendChild(statusSpan);
  scrollToBottom();
}

function appendTextChunk(contentEl, text) {
  // 找到或创建一个 answer-block
  let answerBlock = contentEl.querySelector('.answer-block');
  if (!answerBlock) {
    answerBlock = document.createElement('div');
    answerBlock.className = 'answer-block';
    answerBlock.style.marginTop = '8px';
    answerBlock.style.lineHeight = '1.7';
    contentEl.appendChild(answerBlock);
  }
  answerBlock.textContent += text;
  scrollToBottom();
}

function appendFile(contentEl, path) {
  let filesWrap = contentEl.querySelector('.file-attachments');
  if (!filesWrap) {
    filesWrap = document.createElement('div');
    filesWrap.className = 'file-attachments';
    contentEl.appendChild(filesWrap);
  }
  const chip = document.createElement('span');
  chip.className = 'file-chip';
  chip.innerHTML = `<span class="file-icon">📎</span><span class="file-name"></span>`;
  chip.querySelector('.file-name').textContent = path;
  filesWrap.appendChild(chip);
  scrollToBottom();
}

function appendError(contentEl, reason) {
  const block = makeErrorBlock(reason);
  contentEl.appendChild(block);
}

function makeErrorBlock(text) {
  const div = document.createElement('div');
  div.style.cssText = 'background:#fee2e2;color:#991b1b;padding:8px 12px;border-radius:8px;margin-top:8px;font-size:13px;';
  div.textContent = '⚠️ ' + text;
  return div;
}

// ===========================================
// 任务列表
// ===========================================
async function refreshTaskList() {
  try {
    const res = await fetch('/api/tasks');
    const data = await res.json();
    const tasks = data.tasks || [];

    els.taskCount.textContent = `${tasks.length} 任务`;

    if (tasks.length === 0) {
      els.taskList.innerHTML = '<li class="task-item empty">暂无任务，点击上方按钮创建</li>';
      return;
    }

    // 倒序（最新在上）
    const sorted = [...tasks].reverse();
    els.taskList.innerHTML = sorted.map(t => {
      const statusClass = `status-${t.status === '已完成' ? 'completed' : t.status === '失败' ? 'failed' : 'running'}`;
      const pillClass = statusClass.replace('status-', '');
      const checkbox = t.status === '已完成' ? '☑' : t.status === '失败' ? '✗' : '◐';
      const time = new Date(t.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
      return `
        <li class="task-item ${statusClass} ${t.task_id === state.currentTaskId ? 'active' : ''}" data-task-id="${t.task_id}">
          <span class="task-checkbox">${checkbox}</span>
          <div class="task-content">
            <div class="task-title">${escapeHtml(t.title)}</div>
            <div class="task-meta">
              ${time}
              <span class="task-status-pill ${pillClass}">${t.status}</span>
            </div>
          </div>
          <button class="task-delete" title="删除" data-task-id="${t.task_id}">×</button>
        </li>
      `;
    }).join('');

    // 绑定点击
    els.taskList.querySelectorAll('.task-item').forEach(el => {
      el.addEventListener('click', (e) => {
        if (e.target.classList.contains('task-delete')) return;
        loadTask(el.dataset.taskId);
      });
    });

    // 绑定删除按钮
    els.taskList.querySelectorAll('.task-delete').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteTask(btn.dataset.taskId);
      });
    });
  } catch (e) {
    console.error('刷新任务列表失败:', e);
  }
}

async function deleteTask(taskId) {
  if (!confirm('确定删除此任务？')) return;
  try {
    const res = await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.deleted) {
      // 如果删除的是当前任务，清空聊天区
      if (state.currentTaskId === taskId) {
        newTask();
      }
      refreshTaskList();
    }
  } catch (e) {
    console.error('删除失败:', e);
    alert('删除失败: ' + e.message);
  }
}

async function clearAllTasks() {
  if (!confirm('确定清空所有任务？此操作不可撤销。')) return;
  try {
    const res = await fetch('/api/tasks', { method: 'DELETE' });
    const data = await res.json();
    if (data.cleared !== undefined) {
      state.currentTaskId = null;
      newTask();   // 重置聊天区
    }
  } catch (e) {
    console.error('清空失败:', e);
    alert('清空失败: ' + e.message);
  }
}

async function loadTask(taskId) {
  try {
    const res = await fetch(`/api/tasks/${taskId}`);
    if (!res.ok) return;
    const task = await res.json();

    // 清空聊天区，重放
    els.chatScroll.innerHTML = '';
    state.currentTaskId = taskId;

    // 重放每一步
    const contentEl = appendBotMessage();
    setBotHeader(contentEl, '核心Agent', task.status === '已完成' ? 'completed' : task.status === '失败' ? 'failed' : 'running');

    task.steps.forEach(step => {
      appendThinking(contentEl, `[步骤 ${step.iteration}] ${step.decision.reasoning}`);
      if (step.decision.action === 'call_tool') {
        appendToolCall(contentEl, step.decision.tool_name, step.decision.tool_args);
        if (step.action_result) {
          updateToolResult(contentEl, step.action_result);
        }
      }
    });

    // 显示最终答案
    if (task.final_answer) {
      const block = document.createElement('div');
      block.className = 'answer-block';
      block.style.marginTop = '12px';
      block.style.padding = '12px';
      block.style.background = '#f7f7f8';
      block.style.borderRadius = '8px';
      block.style.lineHeight = '1.7';
      block.style.whiteSpace = 'pre-wrap';
      block.textContent = task.final_answer;
      contentEl.appendChild(block);
    }

    // 文件
    if (task.files && task.files.length) {
      let filesWrap = contentEl.querySelector('.file-attachments');
      if (!filesWrap) {
        filesWrap = document.createElement('div');
        filesWrap.className = 'file-attachments';
        contentEl.appendChild(filesWrap);
      }
      task.files.forEach(f => {
        const chip = document.createElement('span');
        chip.className = 'file-chip';
        chip.innerHTML = `<span class="file-icon">📎</span><span class="file-name"></span>`;
        chip.querySelector('.file-name').textContent = f;
        filesWrap.appendChild(chip);
      });
    }

    scrollToBottom();

    // 标记当前激活
    els.taskList.querySelectorAll('.task-item').forEach(el => {
      el.classList.toggle('active', el.dataset.taskId === taskId);
    });
  } catch (e) {
    console.error('加载任务失败:', e);
  }
}

// ===========================================
// 信息弹窗
// ===========================================
async function showInfo() {
  els.infoModal.style.display = 'flex';
  els.infoBody.innerHTML = '加载中...';

  try {
    const res = await fetch('/api/info');
    const info = await res.json();

    els.infoBody.innerHTML = `
      <div class="cap-section">
        <div class="cap-section-title">📛 名称</div>
        <div class="cap-section-desc">${info.name} (v${info.version})</div>
      </div>

      <div class="cap-section">
        <div class="cap-section-title">🧠 LLM</div>
        <div class="cap-section-desc">${info.llm}</div>
      </div>

      <div class="cap-section">
        <div class="cap-section-title">⚡ 6 项核心能力</div>
        ${Object.entries(info.capabilities).map(([k, v]) => `
          <div style="margin: 4px 0;">
            <strong>${k}</strong>: ${v}
          </div>
        `).join('')}
      </div>

      <div class="cap-section">
        <div class="cap-section-title">🔧 可用工具</div>
        ${info.tools.map(t => `
          <div style="margin: 4px 0;">
            <code style="background:#f7f7f8;padding:1px 6px;border-radius:3px;font-size:12px">${t.name}</code>
            <span style="color:#6b7280;font-size:12px">${t.description}</span>
          </div>
        `).join('') || '<div style="color:#9ca3af">无</div>'}
      </div>

      <div class="cap-section" style="color:#9ca3af;font-size:12px">
        💡 完整能力清单 + 待办事项见 <code>核心Agent/TODO.md</code>
      </div>
    `;
  } catch (e) {
    els.infoBody.innerHTML = `加载失败: ${e.message}`;
  }
}

// ===========================================
// 工具函数
// ===========================================
function scrollToBottom() {
  requestAnimationFrame(() => {
    els.chatScroll.scrollTop = els.chatScroll.scrollHeight;
  });
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ===========================================
// 启动
// ===========================================
refreshTaskList();
els.msgInput.focus();