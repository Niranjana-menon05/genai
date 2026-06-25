// State variables
let state = {
  activeTab: 'dashboard',
  documents: [],
  stats: {
    documents_uploaded: 0,
    questions_asked: 0,
    summaries_generated: 0,
    quizzes_generated: 0
  },
  chatHistory: [],
  selectedDocIds: [],
  // Quiz play state
  quiz: {
    questions: [],
    currentIndex: 0,
    userAnswers: {}, // index -> chosen option or text answer
    revealedAnswers: {}, // index -> boolean (for short/viva self check)
    score: 0
  }
};

const API_BASE = '/api';

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
  // Setup Lucide icons
  lucide.createIcons();
  
  // Load Theme
  initTheme();
  
  // Load dashboard and document data
  refreshData();
  
  // Setup Drag & Drop listeners
  initDragAndDrop();
  
  // Setup Event listeners
  document.getElementById('chat-scope-all')?.addEventListener('click', () => toggleScopeMode('all'));
  
  // Scope selection radios listener
  document.querySelectorAll('input[name="chat-scope"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
      const chatCheckboxContainer = document.getElementById('chat-doc-checklist');
      if (e.target.value === 'all') {
        chatCheckboxContainer.classList.add('opacity-40', 'pointer-events-none');
      } else {
        chatCheckboxContainer.classList.remove('opacity-40', 'pointer-events-none');
      }
    });
  });

  // Default scope state
  const allRadio = document.querySelector('input[name="chat-scope"][value="all"]');
  if (allRadio && allRadio.checked) {
    document.getElementById('chat-doc-checklist')?.classList.add('opacity-40', 'pointer-events-none');
  }

  // Poll for document status periodically (every 5 seconds)
  setInterval(pollProcessingDocuments, 5000);
});

// ================= THEME MANAGEMENT =================

function initTheme() {
  const cachedTheme = localStorage.getItem('theme') || 'light';
  document.documentElement.className = cachedTheme;
  updateThemeIcon(cachedTheme);
}

function toggleDarkMode() {
  const isDark = document.documentElement.classList.contains('dark');
  const nextTheme = isDark ? 'light' : 'dark';
  document.documentElement.className = nextTheme;
  localStorage.setItem('theme', nextTheme);
  updateThemeIcon(nextTheme);
  showNotification(`Switched to ${nextTheme} mode`, 'info');
}

function updateThemeIcon(theme) {
  const icon = document.getElementById('theme-icon');
  if (!icon) return;
  if (theme === 'dark') {
    icon.setAttribute('data-lucide', 'moon');
  } else {
    icon.setAttribute('data-lucide', 'sun');
  }
  lucide.createIcons();
}

// ================= SIDEBAR NAVIGATION =================

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  if (sidebar.classList.contains('-translate-x-full')) {
    sidebar.classList.remove('-translate-x-full');
    overlay.classList.remove('hidden');
  } else {
    sidebar.classList.add('-translate-x-full');
    overlay.classList.add('hidden');
  }
}

function switchTab(tabId) {
  // Update state
  state.activeTab = tabId;
  
  // Hide all panes
  document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.add('hidden'));
  // Show active pane
  document.getElementById(`tab-${tabId}`).classList.remove('hidden');

  // Update navigation button active state
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.classList.remove('active', 'bg-pastel-purple-100', 'dark:bg-purple-950/30', 'text-pastel-purple-700', 'dark:text-purple-300');
    btn.classList.add('text-slate-500', 'dark:text-slate-400');
  });
  
  const activeBtn = document.getElementById(`nav-${tabId}`);
  if (activeBtn) {
    activeBtn.classList.add('active', 'bg-pastel-purple-100', 'dark:bg-purple-950/30', 'text-pastel-purple-700', 'dark:text-purple-300');
    activeBtn.classList.remove('text-slate-500', 'dark:text-slate-400');
  }

  // Update Header Titles
  const titleMap = {
    dashboard: { title: 'Dashboard', subtitle: 'Overview of your study activity.' },
    upload: { title: 'Upload Materials', subtitle: 'Manage slide presentations, notes, and question papers.' },
    chat: { title: 'Chat Assistant', subtitle: 'Retrieval-Augmented Study Q&A with your notes.' },
    revision: { title: 'Revision Notes', subtitle: 'Generate summaries, exam guidelines, and cheat sheets.' },
    pyq: { title: 'PYQ Analyzer', subtitle: 'Match past questions against your current material weights.' },
    quiz: { title: 'Practice Quizzes', subtitle: 'Generate interactive testing cards to challenge yourself.' }
  };
  
  if (titleMap[tabId]) {
    document.getElementById('topbar-title').innerText = titleMap[tabId].title;
    document.getElementById('topbar-subtitle').innerText = titleMap[tabId].subtitle;
  }

  // Close sidebar on mobile
  document.getElementById('sidebar').classList.add('-translate-x-full');
  document.getElementById('sidebar-overlay').classList.add('hidden');

  // Refresh lists if relevant tab opened
  refreshDocChecklists();
}

// ================= DATA REFRESHING & POLLING =================

async function refreshData() {
  await fetchStats();
  await fetchDocuments();
}

async function fetchStats() {
  try {
    const res = await fetch(`${API_BASE}/stats`);
    if (res.ok) {
      state.stats = await res.json();
      updateStatsUI();
    }
  } catch (e) {
    console.error("Failed to fetch statistics:", e);
  }
}

async function fetchDocuments() {
  try {
    const res = await fetch(`${API_BASE}/documents`);
    if (res.ok) {
      state.documents = await res.json();
      updateDocumentsUI();
      refreshDocChecklists();
    }
  } catch (e) {
    console.error("Failed to fetch documents:", e);
  }
}

function pollProcessingDocuments() {
  // Only poll if there are documents in processing status
  const hasProcessing = state.documents.some(doc => 
    doc.status === 'queued' || doc.status === 'processing'
  );
  if (hasProcessing) {
    refreshData();
  }
}

// ================= UI RENDERING UPDATES =================

function updateStatsUI() {
  document.getElementById('stat-docs').innerText = state.stats.documents_uploaded;
  document.getElementById('stat-queries').innerText = state.stats.questions_asked;
  document.getElementById('stat-notes').innerText = state.stats.summaries_generated;
  document.getElementById('stat-quizzes').innerText = state.stats.quizzes_generated;
}

function updateDocumentsUI() {
  // Update library count badge
  const readyDocs = state.documents.filter(d => d.status === 'ready');
  document.getElementById('library-count').innerText = `${state.documents.length} files (${readyDocs.length} ready)`;

  // Render recent documents list on Dashboard
  const dashList = document.getElementById('dashboard-docs-list');
  if (dashList) {
    if (state.documents.length === 0) {
      dashList.innerHTML = `
        <div class="py-10 text-center space-y-2">
          <i data-lucide="folder-open" class="w-8 h-8 text-slate-300 mx-auto"></i>
          <p class="text-xs text-slate-400">No documents uploaded yet.</p>
        </div>
      `;
    } else {
      // Sort: recent first
      const sorted = [...state.documents].reverse().slice(0, 4);
      dashList.innerHTML = sorted.map(doc => {
        const isReady = doc.status === 'ready';
        const isPyq = doc.is_pyq;
        
        let statusBadge = '';
        if (doc.status === 'queued') {
          statusBadge = `<span class="px-2 py-0.5 rounded-full text-[9px] font-bold bg-amber-50 text-amber-600 border border-amber-100">Queued</span>`;
        } else if (doc.status === 'processing') {
          statusBadge = `<span class="px-2 py-0.5 rounded-full text-[9px] font-bold bg-blue-50 text-blue-600 border border-blue-100 animate-pulse">Processing</span>`;
        } else if (doc.status === 'ready') {
          statusBadge = `<span class="px-2 py-0.5 rounded-full text-[9px] font-bold bg-emerald-50 text-emerald-600 border border-emerald-100">Ready</span>`;
        } else {
          statusBadge = `<span class="px-2 py-0.5 rounded-full text-[9px] font-bold bg-rose-50 text-rose-600 border border-rose-100 truncate max-w-[100px]" title="${doc.status}">Error</span>`;
        }

        const typeIcon = getTypeIcon(doc.extension);
        const pyqLabel = isPyq ? `<span class="px-1.5 py-0.5 rounded bg-purple-50 text-purple-600 border border-purple-100 text-[8px] font-bold">PYQ</span>` : '';

        return `
          <div class="flex items-center justify-between p-3 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800/40 border border-slate-50 dark:border-slate-800 transition-all-300">
            <div class="flex items-center gap-3 min-w-0">
              <div class="p-2.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-500">
                <i data-lucide="${typeIcon}" class="w-4 h-4"></i>
              </div>
              <div class="min-w-0">
                <h4 class="font-bold text-xs truncate max-w-[180px] sm:max-w-[280px]" title="${doc.filename}">${doc.filename}</h4>
                <p class="text-[9px] text-slate-400">${formatBytes(doc.file_size)} • ${pyqLabel || 'Lecture Material'}</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              ${statusBadge}
            </div>
          </div>
        `;
      }).join('');
    }
  }

  // Render Document Library Table
  const tableBody = document.getElementById('library-table-body');
  if (tableBody) {
    if (state.documents.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="4" class="py-12 text-center space-y-2">
            <i data-lucide="files" class="w-8 h-8 text-slate-300 mx-auto"></i>
            <p class="text-xs text-slate-400">No documents found. Upload materials to start.</p>
          </td>
        </tr>
      `;
    } else {
      tableBody.innerHTML = state.documents.map(doc => {
        const typeIcon = getTypeIcon(doc.extension);
        let statusHtml = '';
        
        if (doc.status === 'queued') {
          statusHtml = `<span class="px-2.5 py-0.5 rounded-full font-bold bg-amber-50 text-amber-600 border border-amber-100 inline-block text-[10px]">Queued</span>`;
        } else if (doc.status === 'processing') {
          statusHtml = `<span class="px-2.5 py-0.5 rounded-full font-bold bg-blue-50 text-blue-600 border border-blue-100 inline-block text-[10px] animate-pulse">Processing</span>`;
        } else if (doc.status === 'ready') {
          statusHtml = `<span class="px-2.5 py-0.5 rounded-full font-bold bg-emerald-50 text-emerald-600 border border-emerald-100 inline-block text-[10px]">Ready</span>`;
        } else {
          statusHtml = `<span class="px-2.5 py-0.5 rounded-full font-bold bg-rose-50 text-rose-600 border border-rose-100 inline-block text-[10px] truncate max-w-[120px]" title="${doc.status}">Failed</span>`;
        }

        const isPyq = doc.is_pyq;
        const tag = isPyq 
          ? `<span class="px-2 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-100 text-[9px] font-bold">PYQ Paper</span>`
          : `<span class="px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-100 text-[9px] font-bold">Lecture Slide</span>`;

        return `
          <tr class="border-b border-slate-50 dark:border-slate-800/40 hover:bg-slate-50/50 dark:hover:bg-slate-900/10">
            <td class="py-3.5 pr-3">
              <div class="flex items-center gap-3 min-w-0">
                <div class="p-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-400 shrink-0">
                  <i data-lucide="${typeIcon}" class="w-4 h-4"></i>
                </div>
                <div class="min-w-0">
                  <p class="font-bold text-xs text-slate-700 dark:text-slate-200 truncate" title="${doc.filename}">${doc.filename}</p>
                  <p class="text-[10px] text-slate-400">${formatBytes(doc.file_size)} • Uploaded ${doc.uploaded_at}</p>
                </div>
              </div>
            </td>
            <td class="py-3.5">${tag}</td>
            <td class="py-3.5">${statusHtml}</td>
            <td class="py-3.5 text-right">
              <button onclick="handleDeleteDocument('${doc.id}')" class="p-1.5 rounded-lg hover:bg-rose-50 text-slate-400 hover:text-rose-600 transition-all-300" title="Delete document">
                <i data-lucide="trash-2" class="w-4.5 h-4.5"></i>
              </button>
            </td>
          </tr>
        `;
      }).join('');
    }
  }

  // Update Status Badge if Groq Key is connected or using Mock Mode
  const badge = document.getElementById('status-badge');
  if (badge) {
    const isMock = state.documents.length === 0 || !state.stats; // dynamic logic is mocked inside backend
    // Since API handles mock config on server, we can verify mock status from stats response
    // If stats is successfully returned, server is connected
  }

  // Refresh lucide icons
  lucide.createIcons();
}

function refreshDocChecklists() {
  const readyDocs = state.documents.filter(doc => doc.status === 'ready');
  const pyqDocs = readyDocs.filter(doc => doc.is_pyq);
  const noteDocs = readyDocs.filter(doc => !doc.is_pyq);

  // 1. Chat Checklist
  const chatList = document.getElementById('chat-doc-checklist');
  if (chatList) {
    if (readyDocs.length === 0) {
      chatList.innerHTML = `<p class="text-[10px] text-slate-400 italic p-2">No active documents. Upload files to display them here.</p>`;
    } else {
      chatList.innerHTML = readyDocs.map(doc => `
        <label class="flex items-start gap-2 p-1.5 rounded hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer text-[11px] font-semibold">
          <input type="checkbox" name="chat-selected-docs" value="${doc.id}" class="mt-0.5 w-3.5 h-3.5 rounded text-purple-600">
          <span class="truncate" title="${doc.filename}">${doc.filename}</span>
        </label>
      `).join('');
    }
  }

  // 2. Revision Checklist
  const revList = document.getElementById('revision-doc-checklist');
  if (revList) {
    if (noteDocs.length === 0) {
      revList.innerHTML = `<p class="text-[10px] text-slate-400 italic p-2">Upload lecture notes (not PYQ) to reference.</p>`;
    } else {
      revList.innerHTML = noteDocs.map(doc => `
        <label class="flex items-start gap-2 p-1 hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer text-[11px] font-semibold">
          <input type="checkbox" name="revision-selected-docs" value="${doc.id}" checked class="mt-0.5 w-3.5 h-3.5 rounded text-purple-600">
          <span class="truncate" title="${doc.filename}">${doc.filename}</span>
        </label>
      `).join('');
    }
  }

  // 3. Quiz Checklist
  const quizList = document.getElementById('quiz-doc-checklist');
  if (quizList) {
    if (noteDocs.length === 0) {
      quizList.innerHTML = `<p class="text-[10px] text-slate-400 italic p-2">Upload lecture notes to test yourself.</p>`;
    } else {
      quizList.innerHTML = noteDocs.map(doc => `
        <label class="flex items-start gap-2 p-1 hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer text-[11px] font-semibold">
          <input type="checkbox" name="quiz-selected-docs" value="${doc.id}" checked class="mt-0.5 w-3.5 h-3.5 rounded text-purple-600">
          <span class="truncate" title="${doc.filename}">${doc.filename}</span>
        </label>
      `).join('');
    }
  }

  // 4. PYQ Papers Checklist
  const pyqPapersList = document.getElementById('pyq-papers-checklist');
  if (pyqPapersList) {
    if (pyqDocs.length === 0) {
      pyqPapersList.innerHTML = `<p class="text-[10px] text-slate-400 italic p-2">Upload PYQ papers (flagged as PYQ) to select them.</p>`;
    } else {
      pyqPapersList.innerHTML = pyqDocs.map(doc => `
        <label class="flex items-start gap-2 p-1 hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer text-[11px] font-semibold">
          <input type="checkbox" name="pyq-selected-papers" value="${doc.id}" checked class="mt-0.5 w-3.5 h-3.5 rounded text-purple-600">
          <span class="truncate" title="${doc.filename}">${doc.filename}</span>
        </label>
      `).join('');
    }
  }

  // 5. PYQ Matching Notes Checklist
  const pyqNotesList = document.getElementById('pyq-notes-checklist');
  if (pyqNotesList) {
    if (noteDocs.length === 0) {
      pyqNotesList.innerHTML = `<p class="text-[10px] text-slate-400 italic p-2">Upload matching lecture notes.</p>`;
    } else {
      pyqNotesList.innerHTML = noteDocs.map(doc => `
        <label class="flex items-start gap-2 p-1 hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer text-[11px] font-semibold">
          <input type="checkbox" name="pyq-selected-notes" value="${doc.id}" checked class="mt-0.5 w-3.5 h-3.5 rounded text-purple-600">
          <span class="truncate" title="${doc.filename}">${doc.filename}</span>
        </label>
      `).join('');
    }
  }
}

// ================= FILE UPLOAD CONTROLS =================

function initDragAndDrop() {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  
  if (!dropzone) return;

  // Prevent default behaviors
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, preventDefaults, false);
  });

  function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  // Highlight drop area
  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => {
      dropzone.classList.add('border-purple-400', 'bg-purple-50/20', 'dark:bg-purple-950/10');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => {
      dropzone.classList.remove('border-purple-400', 'bg-purple-50/20', 'dark:bg-purple-950/10');
    }, false);
  });

  // Handle drop
  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    handleFilesUpload(files);
  });

  // Handle select
  fileInput.addEventListener('change', (e) => {
    handleFilesUpload(e.target.files);
  });
}

async function handleFilesUpload(files) {
  if (files.length === 0) return;
  
  const isPyq = document.getElementById('upload-is-pyq').checked;
  const queueContainer = document.getElementById('upload-queue-container');
  const queueList = document.getElementById('upload-queue-list');
  
  queueContainer.classList.remove('hidden');
  
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    
    // Add file list card to queue
    const fileId = `upload-file-${Date.now()}-${i}`;
    const fileItemHtml = `
      <div id="${fileId}" class="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-100 dark:border-slate-800 text-[11px] font-semibold space-y-1.5">
        <div class="flex items-center justify-between">
          <span class="truncate max-w-[160px]">${file.name}</span>
          <span class="upload-percent text-slate-400 font-bold">0%</span>
        </div>
        <div class="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
          <div class="upload-progress-bar bg-purple-600 h-full w-0 transition-all-300"></div>
        </div>
      </div>
    `;
    queueList.insertAdjacentHTML('beforeend', fileItemHtml);
    
    // Upload File via Fetch (tracking progress manually using XMLHttpRequest)
    try {
      await uploadFileWithProgress(file, isPyq, fileId);
      showNotification(`"${file.name}" uploaded successfully! Indexing started in background.`, 'success');
    } catch (e) {
      showNotification(`Upload failed for "${file.name}": ${e.message}`, 'error');
      document.getElementById(fileId)?.remove();
    }
  }
  
  // Uncheck checklist PYQ box
  document.getElementById('upload-is-pyq').checked = false;
  // Trigger table reloading
  refreshData();
}

function uploadFileWithProgress(file, isPyq, elementId) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append('file', file);
    formData.append('is_pyq', isPyq);

    // Track upload progress
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 100);
        const container = document.getElementById(elementId);
        if (container) {
          container.querySelector('.upload-percent').innerText = `${percent}%`;
          container.querySelector('.upload-progress-bar').style.width = `${percent}%`;
        }
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        // Success
        setTimeout(() => {
          document.getElementById(elementId)?.remove();
        }, 1000);
        resolve(JSON.parse(xhr.responseText));
      } else {
        // HTTP Error
        const errResponse = JSON.parse(xhr.responseText || '{}');
        reject(new Error(errResponse.detail || 'Server returned an error.'));
      }
    });

    xhr.addEventListener('error', () => reject(new Error('Network error.')));
    
    xhr.open('POST', `${API_BASE}/upload`);
    xhr.send(formData);
  });
}

async function handleDeleteDocument(docId) {
  if (!confirm("Are you sure you want to delete this document? All associated index chunks will be removed.")) {
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/documents/${docId}`, {
      method: 'DELETE'
    });
    if (res.ok) {
      showNotification("Document deleted successfully", "success");
      refreshData();
    } else {
      const err = await res.json();
      showNotification(err.detail || "Failed to delete document", "error");
    }
  } catch (e) {
    showNotification("Failed to delete document", "error");
  }
}

// ================= CHAT ASSISTANT CONTROLS =================

function triggerQuickQuestion(question) {
  document.getElementById('chat-input').value = question;
  document.getElementById('chat-form').dispatchEvent(new Event('submit'));
}

async function handleSendChat(event) {
  event.preventDefault();
  const inputEl = document.getElementById('chat-input');
  const query = inputEl.value.trim();
  if (!query) return;

  // Clear input
  inputEl.value = '';

  // Append user message bubble
  appendChatBubble(query, 'user');

  // Append loading bubble
  const loadingId = appendChatLoadingBubble();

  // Check RAG scope selection
  const scopeMode = document.querySelector('input[name="chat-scope"]:checked').value;
  let docIds = null;
  
  if (scopeMode === 'selected') {
    docIds = Array.from(document.querySelectorAll('input[name="chat-selected-docs"]:checked')).map(cb => cb.value);
    if (docIds.length === 0) {
      removeChatBubble(loadingId);
      appendChatBubble("⚠️ Please select at least one document on the left sidebar to scope your question.", 'assistant', null, true);
      return;
    }
  }

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, doc_ids: docIds })
    });

    removeChatBubble(loadingId);

    if (res.ok) {
      const result = await res.json();
      appendChatBubble(result.answer, 'assistant', result.sources);
      // Increment count dynamically
      state.stats.questions_asked += 1;
      updateStatsUI();
    } else {
      const err = await res.json();
      appendChatBubble(`❌ Error: ${err.detail || 'Failed to connect to assistant.'}`, 'assistant');
    }
  } catch (e) {
    removeChatBubble(loadingId);
    appendChatBubble(`❌ Network error. Check if backend server is running.`, 'assistant');
  }
}

function appendChatBubble(text, sender, sources = null, isError = false) {
  const container = document.getElementById('chat-messages');
  if (!container) return;

  const isUser = sender === 'user';
  const nameLabel = isUser ? 'You' : 'AI Assistant';
  
  // Format basic markdown elements for beautiful rendering
  const formattedText = formatMarkdownToHTML(text);

  let sourcesHtml = '';
  if (sources && sources.length > 0) {
    sourcesHtml = `
      <div class="mt-2.5 pt-2 border-t border-slate-100 dark:border-slate-800 text-[10px] text-slate-400">
        <span class="font-bold uppercase tracking-wider block mb-1">References:</span>
        <div class="flex flex-wrap gap-1">
          ${sources.map(src => `<span class="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 font-semibold border border-slate-200/50 dark:border-slate-800 truncate max-w-[200px]" title="${src}">${src}</span>`).join('')}
        </div>
      </div>
    `;
  }

  const bubbleHtml = isUser ? `
    <div class="flex gap-3 max-w-[85%] ml-auto justify-end">
      <div class="space-y-1 text-right">
        <div class="bg-purple-600 text-white p-4 rounded-2xl rounded-tr-none text-xs leading-relaxed inline-block text-left shadow-sm">
          ${formattedText}
        </div>
      </div>
      <div class="w-8 h-8 rounded-full bg-pastel-purple-200 text-pastel-purple-800 border border-pastel-purple-300 font-bold text-xs flex items-center justify-center shrink-0">
        U
      </div>
    </div>
  ` : `
    <div class="flex gap-3 max-w-[85%]">
      <div class="w-8 h-8 rounded-full bg-pastel-purple-100 text-pastel-purple-700 font-bold text-xs flex items-center justify-center shrink-0">
        AI
      </div>
      <div class="space-y-1">
        <div class="bg-pastel-purple-50 dark:bg-purple-950/20 text-slate-800 dark:text-slate-200 p-4 rounded-2xl rounded-tl-none border border-pastel-purple-100 dark:border-purple-900/20 text-xs leading-relaxed">
          ${formattedText}
          ${sourcesHtml}
        </div>
      </div>
    </div>
  `;

  container.insertAdjacentHTML('beforeend', bubbleHtml);
  container.scrollTop = container.scrollHeight;
}

function appendChatLoadingBubble() {
  const container = document.getElementById('chat-messages');
  if (!container) return null;

  const bubbleId = `chat-load-${Date.now()}`;
  const html = `
    <div id="${bubbleId}" class="flex gap-3 max-w-[85%]">
      <div class="w-8 h-8 rounded-full bg-pastel-purple-100 text-pastel-purple-700 font-bold text-xs flex items-center justify-center shrink-0">
        AI
      </div>
      <div class="bg-pastel-purple-50 dark:bg-purple-950/20 border border-pastel-purple-100 dark:border-purple-900/20 p-4 rounded-2xl rounded-tl-none flex items-center gap-1.5">
        <span class="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style="animation-delay: 0s"></span>
        <span class="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style="animation-delay: 0.15s"></span>
        <span class="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style="animation-delay: 0.3s"></span>
      </div>
    </div>
  `;
  container.insertAdjacentHTML('beforeend', html);
  container.scrollTop = container.scrollHeight;
  return bubbleId;
}

function removeChatBubble(id) {
  document.getElementById(id)?.remove();
}

function clearChat() {
  const container = document.getElementById('chat-messages');
  if (container) {
    container.innerHTML = `
      <div class="flex gap-3 max-w-[85%]">
        <div class="w-8 h-8 rounded-full bg-pastel-purple-100 text-pastel-purple-700 font-bold text-xs flex items-center justify-center shrink-0">
          AI
        </div>
        <div class="bg-pastel-purple-50 dark:bg-purple-950/20 text-slate-800 dark:text-slate-200 p-4 rounded-2xl rounded-tl-none border border-pastel-purple-100 dark:border-purple-900/20 text-xs leading-relaxed">
          <p class="font-semibold text-xs mb-1 text-pastel-purple-800 dark:text-purple-300">Hey there! 👋</p>
          <p>History cleared. Ask me any question from your lectures to begin studying.</p>
        </div>
      </div>
    `;
  }
}

// ================= REVISION NOTES CONTROLS =================

async function handleGenerateRevisionNotes() {
  const topic = document.getElementById('revision-topic').value.trim();
  const noteType = document.querySelector('input[name="note-type"]:checked').value;
  const docIds = Array.from(document.querySelectorAll('input[name="revision-selected-docs"]:checked')).map(cb => cb.value);

  if (!topic) {
    showNotification("Please provide a topic or module name to summarize.", "error");
    return;
  }

  // Display loading skeleton in output panel
  const outputEl = document.getElementById('revision-output-panel');
  outputEl.innerHTML = `
    <div class="space-y-4 py-8">
      <div class="shimmer-bg h-6 rounded-lg w-1/3"></div>
      <div class="shimmer-bg h-4 rounded-lg w-full"></div>
      <div class="shimmer-bg h-4 rounded-lg w-full"></div>
      <div class="shimmer-bg h-4 rounded-lg w-5/6"></div>
      <div class="pt-6 space-y-3">
        <div class="shimmer-bg h-6 rounded-lg w-1/4"></div>
        <div class="shimmer-bg h-4 rounded-lg w-full"></div>
        <div class="shimmer-bg h-4 rounded-lg w-3/4"></div>
      </div>
    </div>
  `;

  try {
    const res = await fetch(`${API_BASE}/revision-notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, note_type: noteType, doc_ids: docIds.length > 0 ? docIds : null })
    });

    if (res.ok) {
      const data = await res.json();
      outputEl.innerHTML = `
        <article class="prose max-w-none text-xs text-slate-700 dark:text-slate-200 leading-relaxed space-y-4">
          ${formatMarkdownToHTML(data.notes)}
        </article>
      `;
      showNotification("Revision notes generated successfully!", "success");
      
      // Increment summaries count
      state.stats.summaries_generated += 1;
      updateStatsUI();
    } else {
      const err = await res.json();
      outputEl.innerHTML = `<div class="p-4 bg-rose-50 text-rose-700 rounded-xl font-semibold text-xs border border-rose-100">Failed: ${err.detail || 'An error occurred'}</div>`;
    }
  } catch (e) {
    outputEl.innerHTML = `<div class="p-4 bg-rose-50 text-rose-700 rounded-xl font-semibold text-xs border border-rose-100">Network error. Check connection.</div>`;
  }
}

function copyRevisionNotes() {
  const panel = document.getElementById('revision-output-panel');
  const text = panel.innerText;
  if (!text || text.includes("No notes generated yet")) return;
  
  navigator.clipboard.writeText(text).then(() => {
    showNotification("Copied output to clipboard!", "success");
  }).catch(() => {
    showNotification("Failed to copy", "error");
  });
}

// ================= PYQ ANALYSIS CONTROLS =================

async function handleAnalyzePYQ() {
  const pyqDocIds = Array.from(document.querySelectorAll('input[name="pyq-selected-papers"]:checked')).map(cb => cb.value);
  const notesDocIds = Array.from(document.querySelectorAll('input[name="pyq-selected-notes"]:checked')).map(cb => cb.value);

  if (pyqDocIds.length === 0) {
    showNotification("Please select at least one uploaded PYQ paper first.", "error");
    return;
  }

  const outputEl = document.getElementById('pyq-output-panel');
  outputEl.innerHTML = `
    <div class="space-y-4 py-8">
      <div class="shimmer-bg h-8 rounded-lg w-1/2"></div>
      <div class="shimmer-bg h-16 rounded-xl w-full"></div>
      <div class="shimmer-bg h-16 rounded-xl w-full"></div>
      <div class="shimmer-bg h-16 rounded-xl w-full"></div>
    </div>
  `;

  try {
    const res = await fetch(`${API_BASE}/pyq-analysis`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pyq_doc_ids: pyqDocIds, notes_doc_ids: notesDocIds.length > 0 ? notesDocIds : null })
    });

    if (res.ok) {
      const data = await res.json();
      renderPYQAnalysis(data.analysis);
      showNotification("PYQ analysis completed!", "success");
    } else {
      const err = await res.json();
      outputEl.innerHTML = `<div class="p-4 bg-rose-50 text-rose-700 rounded-xl font-semibold text-xs border border-rose-100">Failed: ${err.detail || 'An error occurred'}</div>`;
    }
  } catch (e) {
    outputEl.innerHTML = `<div class="p-4 bg-rose-50 text-rose-700 rounded-xl font-semibold text-xs border border-rose-100">Network error. Check connection.</div>`;
  }
}

function renderPYQAnalysis(topics) {
  const outputEl = document.getElementById('pyq-output-panel');
  if (!topics || topics.length === 0) {
    outputEl.innerHTML = `<div class="py-12 text-center text-slate-400">No matching topics discovered.</div>`;
    return;
  }

  // Generate Ranked list with styled visual counts
  // Highest frequency is our baseline for 100% width
  const maxFreq = Math.max(...topics.map(t => t.frequency), 1);

  const listHtml = topics.map((t, idx) => {
    let badgeClass = '';
    let progressBg = '';
    
    if (t.importance === 'High') {
      badgeClass = 'bg-pastel-rose-50 text-pastel-rose-700 border border-pastel-rose-100';
      progressBg = 'bg-rose-450';
    } else if (t.importance === 'Medium') {
      badgeClass = 'bg-pastel-amber-50 text-pastel-amber-700 border border-pastel-amber-100';
      progressBg = 'bg-amber-450';
    } else {
      badgeClass = 'bg-pastel-blue-50 text-pastel-blue-700 border border-pastel-blue-100';
      progressBg = 'bg-sky-450';
    }

    const pct = Math.round((t.frequency / maxFreq) * 100);

    // Questions list html
    let questionsHtml = '';
    if (t.questions && t.questions.length > 0) {
      const questionsList = t.questions.map((qObj, qIdx) => {
        const collapseId = `pyq-collapse-${idx}-${qIdx}`;
        return `
          <div class="border border-slate-100 dark:border-slate-800 rounded-lg overflow-hidden bg-slate-50/50 dark:bg-slate-900/5">
            <button type="button" onclick="toggleCollapse('${collapseId}')" class="w-full flex items-center justify-between p-3 text-left text-xs font-bold text-slate-700 dark:text-slate-350 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all-300">
              <span class="flex items-center gap-2">
                <i data-lucide="help-circle" class="w-3.5 h-3.5 text-purple-500 shrink-0"></i>
                <span class="leading-normal">${qObj.question}</span>
              </span>
              <i id="icon-${collapseId}" data-lucide="chevron-down" class="w-3.5 h-3.5 text-slate-400 transition-transform duration-200 shrink-0"></i>
            </button>
            <div id="${collapseId}" class="hidden p-3 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-650 dark:text-slate-350 bg-white dark:bg-slate-900/10 leading-relaxed space-y-2">
              <div class="font-bold text-[9px] uppercase tracking-wide text-purple-750 dark:text-purple-400 flex items-center gap-1">
                <i data-lucide="book-open" class="w-3 h-3"></i> Solution & Answer:
              </div>
              <div class="whitespace-pre-line text-slate-600 dark:text-slate-400">${formatMarkdownToHTML(qObj.answer)}</div>
            </div>
          </div>
        `;
      }).join('');

      questionsHtml = `
        <div class="mt-4 pt-2 border-t border-slate-50 dark:border-slate-800 space-y-2">
          <p class="text-[10px] font-black uppercase tracking-wider text-purple-600 dark:text-purple-400 flex items-center gap-1">
            <i data-lucide="list-collapse" class="w-3.5 h-3.5"></i> Exam Questions & Solutions (${t.questions.length})
          </p>
          <div class="space-y-2">
            ${questionsList}
          </div>
        </div>
      `;
    }

    return `
      <div class="p-4 rounded-xl border border-slate-100 dark:border-slate-800 space-y-3 bg-white dark:bg-slate-900/10 hover:shadow-sm transition-all-300">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div class="flex items-center gap-2 min-w-0">
            <span class="w-6 h-6 rounded-lg bg-slate-100 dark:bg-slate-800 text-[10px] font-black flex items-center justify-center text-slate-500 shrink-0">#${idx+1}</span>
            <h4 class="font-extrabold text-xs text-slate-700 dark:text-slate-200 truncate" title="${t.topic}">${t.topic}</h4>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <span class="px-2 py-0.5 rounded text-[8px] font-bold ${badgeClass}">${t.importance} Importance</span>
            <span class="text-[10px] text-slate-400 font-bold">${t.frequency} counts</span>
          </div>
        </div>
        
        <!-- Progress bar visual weightage -->
        <div class="space-y-1.5">
          <div class="w-full bg-slate-100 dark:bg-slate-800/80 h-1.5 rounded-full overflow-hidden">
            <div class="h-full ${progressBg} w-0 transition-all-1000" style="width: ${pct}%; background-color: ${t.importance === 'High' ? '#f43f5e' : t.importance === 'Medium' ? '#f59e0b' : '#38bdf8'}"></div>
          </div>
          <div class="text-[11px] text-slate-500 leading-relaxed">${formatMarkdownToHTML(t.description)}</div>
        </div>
        
        <!-- Accordion Questions/Solutions -->
        ${questionsHtml}
      </div>
    `;
  }).join('');

  outputEl.innerHTML = `<div class="space-y-3.5">${listHtml}</div>`;
  lucide.createIcons();
}

// ================= QUIZ GENERATOR CONTROLS =================

async function handleGenerateQuiz() {
  const quizType = document.getElementById('quiz-type').value;
  const difficulty = document.getElementById('quiz-difficulty').value;
  const count = parseInt(document.getElementById('quiz-count').value);
  const docIds = Array.from(document.querySelectorAll('input[name="quiz-selected-docs"]:checked')).map(cb => cb.value);

  // Show global page loader or button loading state
  showNotification("Generating your custom quiz...", "info");

  try {
    const res = await fetch(`${API_BASE}/quiz`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ quiz_type: quizType, difficulty, count, doc_ids: docIds.length > 0 ? docIds : null })
    });

    if (res.ok) {
      const data = await res.json();
      
      // Initialize Quiz Play State
      state.quiz = {
        questions: data.questions,
        currentIndex: 0,
        userAnswers: {},
        revealedAnswers: {},
        score: 0,
        quizType: quizType
      };

      // Transition Panels
      document.getElementById('quiz-setup-panel').classList.add('hidden');
      document.getElementById('quiz-completion-panel').classList.add('hidden');
      document.getElementById('quiz-play-panel').classList.remove('hidden');
      
      renderQuizQuestion();
      showNotification("Quiz loaded! Good luck.", "success");
    } else {
      const err = await res.json();
      showNotification(err.detail || "Failed to generate quiz", "error");
    }
  } catch (e) {
    showNotification("Network error. Verify backend server.", "error");
  }
}

function renderQuizQuestion() {
  const quiz = state.quiz;
  if (!quiz.questions || quiz.questions.length === 0) return;

  const currentQ = quiz.questions[quiz.currentIndex];
  
  // Progress text
  document.getElementById('quiz-progress-text').innerText = `Question ${quiz.currentIndex + 1} of ${quiz.questions.length}`;

  // Question Text
  document.getElementById('quiz-question-text').innerText = currentQ.question;

  // Render options if MCQ, else text field
  const optionsContainer = document.getElementById('quiz-options-container');
  const textContainer = document.getElementById('quiz-text-answer-container');
  const feedbackPanel = document.getElementById('quiz-feedback-panel');

  // Reset feedback
  feedbackPanel.innerHTML = `
    <div class="py-12 text-center text-slate-400 space-y-2">
      <i data-lucide="eye" class="w-8 h-8 text-slate-200 mx-auto"></i>
      <p>Select an option or submit an answer to view explanations.</p>
    </div>
  `;
  lucide.createIcons();

  if (quiz.quizType === 'mcq') {
    optionsContainer.classList.remove('hidden');
    textContainer.classList.add('hidden');

    const chosenAnswer = quiz.userAnswers[quiz.currentIndex];

    optionsContainer.innerHTML = currentQ.options.map((opt, idx) => {
      const isSelected = chosenAnswer === opt;
      const isCorrectOpt = opt === currentQ.correct_answer;
      
      let borderStyle = 'border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40';
      let icon = '';

      if (chosenAnswer !== undefined) {
        // Quiz has been answered
        if (isCorrectOpt) {
          borderStyle = 'border-emerald-300 bg-emerald-50/50 text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-emerald-400';
          icon = '<i data-lucide="check-circle" class="w-4 h-4 text-emerald-600 shrink-0"></i>';
        } else if (isSelected && !isCorrectOpt) {
          borderStyle = 'border-rose-300 bg-rose-50/50 text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/20 dark:text-rose-400';
          icon = '<i data-lucide="alert-circle" class="w-4 h-4 text-rose-600 shrink-0"></i>';
        } else {
          borderStyle = 'border-slate-200 dark:border-slate-800 opacity-60';
        }
      }

      // Disabled if answered
      const disabledAttr = chosenAnswer !== undefined ? 'disabled' : '';

      return `
        <button onclick="submitMCQAnswer('${opt.replace(/'/g, "\\'")}')" ${disabledAttr} class="w-full text-left p-3.5 rounded-xl border text-xs font-semibold flex items-center justify-between gap-3 transition-all-300 ${borderStyle}">
          <span>${opt}</span>
          ${icon}
        </button>
      `;
    }).join('');

    // If already answered, reveal feedback panel
    if (chosenAnswer !== undefined) {
      revealMCQFeedback(chosenAnswer === currentQ.correct_answer);
    }

  } else {
    // Short or Viva Q
    optionsContainer.classList.add('hidden');
    textContainer.classList.remove('hidden');

    const writtenVal = quiz.userAnswers[quiz.currentIndex] || '';
    const textInput = document.getElementById('quiz-text-answer');
    textInput.value = writtenVal;

    // Disabled status
    const isRevealed = quiz.revealedAnswers[quiz.currentIndex] === true;
    if (isRevealed) {
      textInput.disabled = true;
      revealTextAnswerFeedback();
    } else {
      textInput.disabled = false;
    }
  }

  // Update navigation button status
  document.getElementById('quiz-prev-btn').disabled = quiz.currentIndex === 0;

  const isLast = quiz.currentIndex === quiz.questions.length - 1;
  const nextBtn = document.getElementById('quiz-next-btn');
  nextBtn.innerText = isLast ? 'Finish Quiz' : 'Next Question';

  lucide.createIcons();
}

function submitMCQAnswer(chosenOption) {
  const quiz = state.quiz;
  const currentQ = quiz.questions[quiz.currentIndex];

  // Save answer
  quiz.userAnswers[quiz.currentIndex] = chosenOption;
  
  const isCorrect = chosenOption === currentQ.correct_answer;
  if (isCorrect) {
    quiz.score += 1;
  }

  // Rerender question to show selected/correct outlines
  renderQuizQuestion();
}

function revealMCQFeedback(isCorrect) {
  const currentQ = state.quiz.questions[state.quiz.currentIndex];
  const panel = document.getElementById('quiz-feedback-panel');

  const titleText = isCorrect ? 'Correct Answer!' : 'Incorrect Answer';
  const titleClass = isCorrect ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-700 dark:text-rose-400';
  const icon = isCorrect ? 'check-check' : 'x';
  const bgClass = isCorrect ? 'bg-pastel-mint-50 dark:bg-emerald-950/20 border-pastel-mint-100' : 'bg-pastel-rose-50 dark:bg-rose-950/20 border-pastel-rose-100';

  panel.innerHTML = `
    <div class="p-4 rounded-xl border ${bgClass} space-y-2.5">
      <h4 class="font-extrabold text-xs flex items-center gap-2 ${titleClass}">
        <i data-lucide="${icon}" class="w-4.5 h-4.5"></i> ${titleText}
      </h4>
      <p class="text-[11px] leading-relaxed text-slate-600 dark:text-slate-350">${currentQ.explanation}</p>
    </div>
  `;
  lucide.createIcons();
}

function revealTextAnswer() {
  const textVal = document.getElementById('quiz-text-answer').value.trim();
  const quiz = state.quiz;
  
  // Store written text
  quiz.userAnswers[quiz.currentIndex] = textVal;
  quiz.revealedAnswers[quiz.currentIndex] = true;

  // Disable text area
  document.getElementById('quiz-text-answer').disabled = true;

  // Show feedback
  revealTextAnswerFeedback();
}

function revealTextAnswerFeedback() {
  const currentQ = state.quiz.questions[state.quiz.currentIndex];
  const panel = document.getElementById('quiz-feedback-panel');

  panel.innerHTML = `
    <div class="space-y-4">
      <div class="p-4 rounded-xl border bg-pastel-blue-50 border-pastel-blue-100 dark:bg-sky-950/20 dark:border-sky-900/40 space-y-2">
        <h4 class="font-extrabold text-xs text-pastel-blue-700 dark:text-sky-400 flex items-center gap-1.5">
          <i data-lucide="key-round" class="w-4 h-4"></i> Sample Ideal Answer:
        </h4>
        <p class="text-[11px] leading-relaxed text-slate-700 dark:text-slate-300">${currentQ.sample_answer}</p>
      </div>

      <div class="p-4 rounded-xl border bg-slate-50 border-slate-100 dark:bg-slate-900/40 dark:border-slate-800 space-y-2">
        <h4 class="font-extrabold text-xs text-slate-500 flex items-center gap-1.5">
          <i data-lucide="award" class="w-4 h-4"></i> Evaluation Key Points:
        </h4>
        <p class="text-[11px] leading-relaxed text-slate-600 dark:text-slate-400">${currentQ.explanation}</p>
      </div>

      <!-- Self Evaluation Score selection for short answers -->
      <div class="p-3 rounded-xl border border-dashed border-slate-200 dark:border-slate-800/80 flex items-center justify-between bg-white dark:bg-transparent">
        <span class="text-[10px] font-bold text-slate-500 uppercase">Self Grade:</span>
        <div class="flex gap-2">
          <button onclick="setSelfScore(0)" class="px-2.5 py-1.5 rounded-lg border text-[10px] font-bold hover:bg-rose-50 text-rose-600">Incorrect</button>
          <button onclick="setSelfScore(1)" class="px-2.5 py-1.5 rounded-lg border text-[10px] font-bold hover:bg-emerald-50 text-emerald-600">Correct</button>
        </div>
      </div>
    </div>
  `;
  lucide.createIcons();
}

function setSelfScore(val) {
  state.quiz.userAnswers[`score_${state.quiz.currentIndex}`] = val;
  showNotification(val === 1 ? "Marked as correct!" : "Marked as incorrect.", "info");
}

function prevQuestion() {
  if (state.quiz.currentIndex > 0) {
    state.quiz.currentIndex -= 1;
    renderQuizQuestion();
  }
}

function nextQuestion() {
  const quiz = state.quiz;
  const isLast = quiz.currentIndex === quiz.questions.length - 1;

  if (isLast) {
    // Finish Quiz and transition
    calculateFinalScore();
    showQuizCompletionScreen();
  } else {
    quiz.currentIndex += 1;
    renderQuizQuestion();
  }
}

function calculateFinalScore() {
  const quiz = state.quiz;
  
  if (quiz.quizType === 'mcq') {
    // Scores are updated directly during choice click
  } else {
    // Count self grades
    let selfGradeScore = 0;
    for (let i = 0; i < quiz.questions.length; i++) {
      if (quiz.userAnswers[`score_${i}`] === 1) {
        selfGradeScore += 1;
      }
    }
    quiz.score = selfGradeScore;
  }
}

function showQuizCompletionScreen() {
  document.getElementById('quiz-play-panel').classList.add('hidden');
  document.getElementById('quiz-completion-panel').classList.remove('hidden');

  const finalScoreEl = document.getElementById('quiz-final-score');
  finalScoreEl.innerText = `${state.quiz.score} / ${state.quiz.questions.length}`;

  // Update total stats locally and trigger api increment on server
  updateStatOnServer('quizzes_generated'); // track completed quiz count
}

function resetQuizInterface() {
  document.getElementById('quiz-play-panel').classList.add('hidden');
  document.getElementById('quiz-completion-panel').classList.add('hidden');
  document.getElementById('quiz-setup-panel').classList.remove('hidden');
}

async function updateStatOnServer(key) {
  try {
    // Simple way to let the server know we finished a quiz or action
    // backend main.py automatically updates stats in metadata when routes are called,
    // this acts as a refresh sync
    fetchStats();
  } catch (e) {}
}

// ================= NOTIFICATION HELPER =================

function showNotification(message, type = 'success') {
  const banner = document.getElementById('notification-banner');
  if (!banner) return;

  // Clear previous classes
  banner.className = "fixed bottom-6 right-6 px-4 py-3 rounded-xl shadow-lg border text-xs font-bold transition-all-300 z-50 flex items-center gap-2";
  
  let bgBorderClass = '';
  let iconName = '';
  
  if (type === 'success') {
    bgBorderClass = 'bg-pastel-mint-50 text-pastel-mint-700 border-pastel-mint-100 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-900';
    iconName = 'check-circle-2';
  } else if (type === 'error') {
    bgBorderClass = 'bg-pastel-rose-50 text-pastel-rose-700 border-pastel-rose-100 dark:bg-rose-950 dark:text-rose-300 dark:border-rose-900';
    iconName = 'alert-triangle';
  } else {
    bgBorderClass = 'bg-pastel-blue-50 text-pastel-blue-700 border-pastel-blue-100 dark:bg-sky-950 dark:text-sky-300 dark:border-sky-900';
    iconName = 'info';
  }

  banner.classList.add(...bgBorderClass.split(' '));
  banner.innerHTML = `<i data-lucide="${iconName}" class="w-4 h-4 shrink-0"></i> <span>${message}</span>`;
  lucide.createIcons();

  // Slide in
  banner.classList.remove('translate-y-24', 'opacity-0');
  
  // Hide after 3 seconds
  setTimeout(() => {
    banner.classList.add('translate-y-24', 'opacity-0');
  }, 3500);
}

// ================= STRING & BYTE HELPERS =================

function formatBytes(bytes, decimals = 2) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function getTypeIcon(ext) {
  switch (ext.toLowerCase()) {
    case '.pdf': return 'file-text';
    case '.pptx':
    case '.ppt': return 'presentation';
    case '.docx': return 'file-edit';
    case '.txt':
    case '.md': return 'file-signature';
    default: return 'file';
  }
}

function formatMarkdownToHTML(text) {
  if (!text) return '';
  
  // Escape HTML tags to prevent XSS (except headers / code we introduce)
  let clean = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Bold
  clean = clean.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  
  // Inline code
  clean = clean.replace(/`(.*?)`/g, '<code class="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 font-mono text-[11px]">$1</code>');
  
  // Bullet lists (bullet point start line)
  clean = clean.replace(/^\s*[\*\-]\s+(.*?)$/gm, '<li class="ml-4 list-disc pb-1">$1</li>');

  // Ordered lists
  clean = clean.replace(/^\s*\d+\.\s+(.*?)$/gm, '<li class="ml-4 list-decimal pb-1">$1</li>');

  // Headers (h3, h4)
  clean = clean.replace(/^###\s+(.*?)$/gm, '<h4 class="font-extrabold text-xs text-indigo-600 dark:text-indigo-400 mt-4 mb-2">$1</h4>');
  clean = clean.replace(/^##\s+(.*?)$/gm, '<h3 class="font-extrabold text-sm text-slate-800 dark:text-slate-100 mt-5 mb-2.5 pb-1 border-b border-slate-100 dark:border-slate-800">$1</h3>');
  clean = clean.replace(/^#\s+(.*?)$/gm, '<h2 class="font-extrabold text-md text-slate-900 dark:text-white mt-6 mb-3">$1</h2>');

  // LaTeX inline blocks (math brackets)
  clean = clean.replace(/\\\((.*?)\\\)/g, '<span class="font-mono text-indigo-500 italic">$1</span>');
  clean = clean.replace(/\\\[(.*?)\\\]/g, '<div class="my-2 p-2 bg-slate-50 dark:bg-slate-900/30 rounded border border-slate-100 dark:border-slate-800 text-center font-mono text-indigo-500">$1</div>');

  // Replace double linebreaks with paragraphs
  clean = clean.replace(/\n\n/g, '</p><p class="mt-2">');

  return `<p>${clean}</p>`;
}

// Collapsible helper function for PYQ accordion questions
function toggleCollapse(id) {
  const panel = document.getElementById(id);
  const icon = document.getElementById(`icon-${id}`);
  if (panel && icon) {
    if (panel.classList.contains('hidden')) {
      panel.classList.remove('hidden');
      icon.classList.add('rotate-180');
    } else {
      panel.classList.add('hidden');
      icon.classList.remove('rotate-180');
    }
  }
}
window.toggleCollapse = toggleCollapse;
