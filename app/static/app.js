const state = {
  sessionId: null,
  busy: false,
};

const els = {
  chat: document.getElementById('chat'),
  itinerary: document.getElementById('itinerary'),
  slots: document.getElementById('slots'),
  form: document.getElementById('composer'),
  input: document.getElementById('message'),
  send: document.getElementById('send'),
  newSession: document.getElementById('new-session'),
};

const SLOT_LABELS = {
  destination: '目的地',
  days: '天数',
  preferences: '偏好',
  budget_level: '预算',
  travelers: '人数',
  accommodation: '住宿',
  start_date: '出发',
};

const BUDGET_LABELS = {
  lodging: '住宿',
  food: '餐饮',
  local_transport: '市内交通',
  tickets: '门票',
  total: '总计',
};

const SOURCE_LABELS = {
  tavily: 'Tavily 景点搜索',
  'wttr.in': 'wttr.in 天气',
  estimate: '本地预算估算',
};

function setBusy(busy) {
  state.busy = busy;
  els.send.disabled = busy;
}

async function createSession() {
  const response = await fetch('/api/session', { method: 'POST' });
  if (!response.ok) {
    throw new Error(`创建会话失败（${response.status}）`);
  }
  const data = await response.json();
  state.sessionId = data.session_id;
}

function addBubble(role, text) {
  const bubble = document.createElement('div');
  bubble.className = `bubble bubble-${role}`;
  bubble.textContent = text;
  els.chat.appendChild(bubble);
  els.chat.scrollTop = els.chat.scrollHeight;
  return bubble;
}

function appendToken(bubble, text) {
  bubble.textContent += text;
  els.chat.scrollTop = els.chat.scrollHeight;
}

function showError(message) {
  const bubble = document.createElement('div');
  bubble.className = 'bubble bubble-error';
  bubble.textContent = message;
  els.chat.appendChild(bubble);
  els.chat.scrollTop = els.chat.scrollHeight;
}

function updateProfile(profile) {
  const values = {
    destination: profile.destination,
    days: profile.days ? `${profile.days} 天` : null,
    preferences:
      profile.preferences && profile.preferences.length
        ? profile.preferences.join('、')
        : null,
    budget_level: profile.budget_level,
    travelers: profile.travelers ? `${profile.travelers} 人` : null,
    accommodation: profile.accommodation,
    start_date: profile.start_date,
  };

  for (const chip of els.slots.querySelectorAll('.chip')) {
    const slot = chip.dataset.slot;
    const label = SLOT_LABELS[slot] || slot;
    const value = values[slot];
    chip.textContent = `${label}：${value || '待填写'}`;
    chip.classList.toggle('filled', Boolean(value));
  }
}

function money(value) {
  return `¥${Number(value).toLocaleString('zh-CN')}`;
}

function renderDay(day) {
  const section = document.createElement('article');
  section.className = 'day-card';

  const header = document.createElement('header');
  const title = document.createElement('h3');
  title.textContent = `第 ${day.day_index} 天 · ${day.theme || ''}`;
  const dateLabel = document.createElement('span');
  dateLabel.className = 'day-date';
  dateLabel.textContent = day.date || '';
  header.append(title, dateLabel);
  section.appendChild(header);

  if (day.weather) {
    const weather = document.createElement('p');
    weather.className = 'weather';
    if (day.weather.unavailable) {
      weather.textContent = `天气：${day.weather.weather_desc || '暂无预报'}`;
      weather.classList.add('muted');
    } else {
      const parts = [`天气：${day.weather.weather_desc || '未知'}`];
      const low = day.weather.temp_low_c;
      const high = day.weather.temp_high_c;
      if (low !== null && low !== undefined && high !== null && high !== undefined) {
        parts.push(`${low}℃ ~ ${high}℃`);
      }
      if (day.weather.chance_of_rain !== null && day.weather.chance_of_rain !== undefined) {
        parts.push(`降雨概率 ${day.weather.chance_of_rain}%`);
      }
      if (day.weather.suggestion) {
        parts.push(day.weather.suggestion);
      }
      weather.textContent = parts.join(' · ');
    }
    section.appendChild(weather);
  }

  const list = document.createElement('ol');
  list.className = 'timeline';
  for (const activity of day.activities || []) {
    const item = document.createElement('li');

    const time = document.createElement('span');
    time.className = 'time';
    time.textContent = activity.time || '';

    const body = document.createElement('div');
    body.className = 'activity';

    const name = document.createElement('strong');
    name.textContent = activity.name || '';

    const meta = document.createElement('span');
    meta.className = 'muted';
    const metaParts = [];
    if (activity.duration_min) {
      metaParts.push(`${activity.duration_min} 分钟`);
    }
    if (activity.cost_estimate) {
      metaParts.push(
        `${money(activity.cost_estimate.min)}–${money(activity.cost_estimate.max)}`
      );
    }
    meta.textContent = metaParts.join(' · ');

    const description = document.createElement('p');
    description.textContent = activity.description || '';

    body.append(name, meta, description);
    if (activity.source_url) {
      const link = document.createElement('a');
      link.href = activity.source_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = '查看来源';
      body.appendChild(link);
    }

    item.append(time, body);
    list.appendChild(item);
  }
  section.appendChild(list);

  if (day.accommodation) {
    const accommodation = document.createElement('p');
    accommodation.className = 'accommodation';
    accommodation.textContent = `住宿：${day.accommodation}`;
    section.appendChild(accommodation);
  }

  return section;
}

function renderBudget(budget) {
  const table = document.createElement('table');
  table.className = 'budget-table';

  const caption = document.createElement('caption');
  caption.textContent = '预算估算';
  table.appendChild(caption);

  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  for (const label of ['项目', '区间']) {
    const cell = document.createElement('th');
    cell.textContent = label;
    headRow.appendChild(cell);
  }
  head.appendChild(headRow);
  table.appendChild(head);

  const body = document.createElement('tbody');
  for (const [key, label] of Object.entries(BUDGET_LABELS)) {
    const range = budget && budget[key];
    if (!range) {
      continue;
    }
    const row = document.createElement('tr');
    if (key === 'total') {
      row.className = 'total-row';
    }
    const nameCell = document.createElement('td');
    nameCell.textContent = label;
    const valueCell = document.createElement('td');
    valueCell.textContent = `${money(range.min)} – ${money(range.max)}`;
    row.append(nameCell, valueCell);
    body.appendChild(row);
  }
  table.appendChild(body);

  return table;
}

function renderSources(sources) {
  const footer = document.createElement('p');
  footer.className = 'sources';
  const names = (sources || []).map((source) => SOURCE_LABELS[source] || source);
  footer.textContent = names.length
    ? `数据来源：${names.join(' · ')}`
    : '数据来源：本地估算';
  return footer;
}

function renderItinerary(itinerary) {
  els.itinerary.replaceChildren();

  const heading = document.createElement('h2');
  heading.textContent = `${itinerary.city} · ${itinerary.days} 天行程`;
  els.itinerary.appendChild(heading);

  if (itinerary.summary) {
    const summary = document.createElement('p');
    summary.className = 'summary';
    summary.textContent = itinerary.summary;
    els.itinerary.appendChild(summary);
  }

  for (const day of itinerary.day_plans || []) {
    els.itinerary.appendChild(renderDay(day));
  }

  if (itinerary.budget) {
    els.itinerary.appendChild(renderBudget(itinerary.budget));
  }
  els.itinerary.appendChild(renderSources(itinerary.data_sources));

  els.itinerary.classList.remove('hidden');
  els.itinerary.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function handleEvent(event, data, assistantBubble) {
  switch (event) {
    case 'session':
      state.sessionId = data.session_id;
      break;
    case 'profile':
      updateProfile(data);
      break;
    case 'token':
      appendToken(assistantBubble, data.text || '');
      break;
    case 'itinerary':
      renderItinerary(data);
      break;
    case 'error':
      showError(data.message || '发生错误，请重试。');
      break;
    default:
      break;
  }
}

function handleBlock(block, assistantBubble) {
  if (!block.trim()) {
    return;
  }
  let event = 'message';
  const dataLines = [];
  for (const line of block.split('\n')) {
    if (line.startsWith('event: ')) {
      event = line.slice(7);
    } else if (line.startsWith('data: ')) {
      dataLines.push(line.slice(6));
    }
  }
  if (!dataLines.length) {
    return;
  }
  let data;
  try {
    data = JSON.parse(dataLines.join('\n'));
  } catch (error) {
    return;
  }
  handleEvent(event, data, assistantBubble);
}

async function streamChat(message, assistantBubble) {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: state.sessionId }),
  });

  if (!response.ok) {
    let detail = `请求失败（${response.status}）`;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch (error) {
      // 保留默认错误信息
    }
    throw new Error(detail);
  }

  if (!response.body) {
    throw new Error('当前浏览器不支持流式响应');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    let boundary;
    while ((boundary = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      handleBlock(block, assistantBubble);
    }
  }

  if (buffer.trim()) {
    handleBlock(buffer, assistantBubble);
  }
}

async function sendMessage(text) {
  addBubble('user', text);
  const assistantBubble = addBubble('assistant', '');
  assistantBubble.classList.add('typing');
  setBusy(true);

  try {
    if (!state.sessionId) {
      await createSession();
    }
    await streamChat(text, assistantBubble);
  } catch (error) {
    showError(error.message || String(error));
  } finally {
    assistantBubble.classList.remove('typing');
    if (!assistantBubble.textContent.trim()) {
      assistantBubble.remove();
    }
    setBusy(false);
  }
}

function resetSlots() {
  for (const chip of els.slots.querySelectorAll('.chip')) {
    const slot = chip.dataset.slot;
    const label = SLOT_LABELS[slot] || slot;
    const defaults = { budget_level: '舒适', travelers: '1 人', accommodation: '酒店' };
    const value = defaults[slot];
    chip.textContent = `${label}：${value || '待填写'}`;
    chip.classList.toggle('filled', Boolean(value));
  }
}

els.form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const text = els.input.value.trim();
  if (!text || state.busy) {
    return;
  }
  els.input.value = '';
  await sendMessage(text);
});

els.input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    els.form.requestSubmit();
  }
});

els.newSession.addEventListener('click', async () => {
  if (state.busy) {
    return;
  }
  state.sessionId = null;
  els.chat.replaceChildren();
  els.itinerary.replaceChildren();
  els.itinerary.classList.add('hidden');
  resetSlots();
  try {
    await createSession();
  } catch (error) {
    showError(error.message || String(error));
    return;
  }
  addBubble('assistant', '你好！想去哪里旅行？可以告诉我目的地、天数和偏好。');
});

async function init() {
  try {
    await createSession();
    addBubble('assistant', '你好！想去哪里旅行？可以告诉我目的地、天数和偏好。');
  } catch (error) {
    showError(error.message || String(error));
  }
}

init();
