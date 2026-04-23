/**
 * Beetel Song Manager — Client-side logic
 * AJAX CRUD, modals, search, toasts, Spotify lookup
 */

// ── Toast Notifications ───────────────────────────────

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const icons = {
    success: '✓',
    error: '✕',
    info: 'ℹ',
  };

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || icons.info}</span>
    <span class="toast-message">${message}</span>
    <button class="toast-close" onclick="this.parentElement.remove()">×</button>
  `;

  container.appendChild(toast);

  // Auto-remove after 4s
  setTimeout(() => {
    toast.classList.add('removing');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}


// ── Modal Management ──────────────────────────────────

function openModal(mode = 'add', songData = null) {
  const overlay = document.getElementById('song-modal-overlay');
  const title = document.getElementById('modal-title');
  const form = document.getElementById('song-form');
  const submitBtn = document.getElementById('modal-submit-btn');

  // Reset form
  form.reset();
  document.getElementById('form-song-id').value = '';
  clearFormErrors();

  if (mode === 'edit' && songData) {
    title.textContent = 'Edit Song';
    submitBtn.textContent = 'Save Changes';
    document.getElementById('form-song-id').value = songData.id;
    document.getElementById('form-dial-code').value = songData.dial_code;
    document.getElementById('form-spotify-uri').value = songData.spotify_uri;
    document.getElementById('form-song-name').value = songData.song_name;
    document.getElementById('form-artist').value = songData.artist;
    document.getElementById('form-is-playlist').checked = songData.is_playlist;
    document.getElementById('form-active').checked = songData.active;
  } else {
    title.textContent = 'Add New Song';
    submitBtn.textContent = 'Add Song';
    document.getElementById('form-active').checked = true;
  }

  overlay.classList.add('open');
  setTimeout(() => document.getElementById('form-dial-code').focus(), 200);
}

function closeModal() {
  const overlay = document.getElementById('song-modal-overlay');
  overlay.classList.remove('open');
}

function clearFormErrors() {
  document.querySelectorAll('.form-error').forEach(el => el.textContent = '');
}


// ── Song CRUD ─────────────────────────────────────────

async function saveSong() {
  clearFormErrors();

  const songId = document.getElementById('form-song-id').value;
  const data = {
    dial_code: document.getElementById('form-dial-code').value.trim(),
    spotify_uri: document.getElementById('form-spotify-uri').value.trim(),
    song_name: document.getElementById('form-song-name').value.trim(),
    artist: document.getElementById('form-artist').value.trim(),
    is_playlist: document.getElementById('form-is-playlist').checked,
    active: document.getElementById('form-active').checked,
  };

  // Client-side validation
  if (!data.dial_code) {
    showFieldError('dial-code', 'Dial code is required');
    return;
  }
  if (!/^\d{1,6}$/.test(data.dial_code)) {
    showFieldError('dial-code', 'Must be 1–6 digits');
    return;
  }
  if (!data.spotify_uri) {
    showFieldError('spotify-uri', 'Spotify URI or URL is required');
    return;
  }

  const submitBtn = document.getElementById('modal-submit-btn');
  const origText = submitBtn.textContent;
  submitBtn.innerHTML = '<span class="spinner"></span> Saving…';
  submitBtn.disabled = true;

  try {
    const isEdit = !!songId;
    const url = isEdit ? `/songs/${songId}` : '/songs';
    const method = isEdit ? 'PUT' : 'POST';

    const resp = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    const result = await resp.json();

    if (!resp.ok) {
      const errorMsg = result.error || result.detail || 'Something went wrong';
      showToast(errorMsg, 'error');

      // Show field-level error for duplicate dial code
      if (resp.status === 409) {
        showFieldError('dial-code', errorMsg);
      }
      return;
    }

    showToast(isEdit ? 'Song updated!' : 'Song added!', 'success');
    closeModal();
    setTimeout(() => location.reload(), 500);
  } catch (err) {
    showToast('Network error — check your connection', 'error');
  } finally {
    submitBtn.textContent = origText;
    submitBtn.disabled = false;
  }
}

function showFieldError(field, message) {
  const el = document.getElementById(`error-${field}`);
  if (el) el.textContent = message;
}


// ── Delete Song ───────────────────────────────────────

let pendingDeleteId = null;

function confirmDelete(songId, songName) {
  pendingDeleteId = songId;
  const overlay = document.getElementById('confirm-overlay');
  const msg = document.getElementById('confirm-message');
  msg.textContent = `Delete "${songName}"? This cannot be undone.`;
  overlay.classList.add('open');
}

function cancelDelete() {
  pendingDeleteId = null;
  document.getElementById('confirm-overlay').classList.remove('open');
}

async function executeDelete() {
  if (!pendingDeleteId) return;

  try {
    const resp = await fetch(`/songs/${pendingDeleteId}`, { method: 'DELETE' });
    if (resp.ok) {
      showToast('Song deleted', 'success');
      cancelDelete();
      setTimeout(() => location.reload(), 500);
    } else {
      const result = await resp.json();
      showToast(result.error || 'Failed to delete', 'error');
    }
  } catch (err) {
    showToast('Network error', 'error');
  }
}


// ── Spotify Lookup ────────────────────────────────────

async function spotifyLookup() {
  const uriInput = document.getElementById('form-spotify-uri');
  const uri = uriInput.value.trim();
  if (!uri) {
    showFieldError('spotify-uri', 'Enter a Spotify URL or URI first');
    return;
  }

  const btn = document.getElementById('lookup-btn');
  const origText = btn.textContent;
  btn.innerHTML = '<span class="spinner"></span>';
  btn.disabled = true;

  try {
    const resp = await fetch('/spotify/lookup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ uri }),
    });

    const result = await resp.json();

    if (resp.ok) {
      document.getElementById('form-song-name').value = result.song_name || '';
      document.getElementById('form-artist').value = result.artist || '';
      document.getElementById('form-is-playlist').checked = result.is_playlist || false;
      showToast('Metadata loaded from Spotify', 'success');
    } else {
      showToast(result.error || 'Lookup failed', 'error');
    }
  } catch (err) {
    showToast('Network error during lookup', 'error');
  } finally {
    btn.textContent = origText;
    btn.disabled = false;
  }
}


// ── Search / Filter ───────────────────────────────────

function initSearch() {
  const input = document.getElementById('search-input');
  if (!input) return;

  input.addEventListener('input', () => {
    const query = input.value.toLowerCase().trim();
    const rows = document.querySelectorAll('.song-table tbody tr');

    rows.forEach(row => {
      if (row.classList.contains('empty-row')) return;
      const text = row.textContent.toLowerCase();
      row.style.display = text.includes(query) ? '' : 'none';
    });
  });
}


// ── Settings: Test Spotify ────────────────────────────

async function testSpotify() {
  const btn = document.getElementById('test-spotify-btn');
  const result = document.getElementById('spotify-test-result');
  const origText = btn.textContent;
  btn.innerHTML = '<span class="spinner"></span> Testing…';
  btn.disabled = true;
  result.textContent = '';

  try {
    const resp = await fetch('/spotify/test', { method: 'POST' });
    const data = await resp.json();

    result.textContent = data.message;
    result.className = data.ok ? 'form-hint' : 'form-error';

    showToast(data.message, data.ok ? 'success' : 'error');
  } catch (err) {
    result.textContent = 'Network error';
    result.className = 'form-error';
  } finally {
    btn.textContent = origText;
    btn.disabled = false;
  }
}


// ── Copy to Clipboard ─────────────────────────────────

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast('Copied to clipboard', 'info');
  });
}


// ── Toggle Quick Active Status ────────────────────────

async function toggleActive(songId, currentlyActive) {
  try {
    const resp = await fetch(`/songs/${songId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active: !currentlyActive }),
    });

    if (resp.ok) {
      showToast(currentlyActive ? 'Song deactivated' : 'Song activated', 'success');
      setTimeout(() => location.reload(), 400);
    }
  } catch (err) {
    showToast('Failed to update status', 'error');
  }
}


// ── Close modal on Escape / overlay click ─────────────

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeModal();
    cancelDelete();
  }
});

document.addEventListener('click', (e) => {
  if (e.target.id === 'song-modal-overlay') closeModal();
  if (e.target.id === 'confirm-overlay') cancelDelete();
});


// ── Init ──────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  initSearch();
});
