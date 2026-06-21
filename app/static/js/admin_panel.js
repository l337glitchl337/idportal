const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
const _cfg = JSON.parse(document.getElementById('app-config').textContent);
const batchEditUrl = _cfg.batchEditUrl;
const approveUrl   = _cfg.approveUrl;
const rejectUrl    = _cfg.rejectUrl;
const deleteUrl    = _cfg.deleteUrl;

function escapeHtml(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(String(str)));
  return div.innerHTML;
}

function showResultModal(success, message, errors = {}) {
  const modalTitle = document.getElementById('resultModalTitle');
  const modalBody = document.getElementById('resultModalBody');
  const modalErrors = document.getElementById('resultModalErrors');

  if (!modalTitle || !modalBody || !modalErrors) {
    console.error("Modal elements not found in the DOM.");
    return;
  }

  modalTitle.textContent = success ? "Success" : "Error";
  modalBody.textContent = message;

  if (Object.keys(errors).length > 0) {
    const errorList = Object.entries(errors)
      .map(([id, error]) => `<li>Request ID ${escapeHtml(id)}: ${escapeHtml(error)}</li>`)
      .join('');
    modalErrors.innerHTML = `<ul>${errorList}</ul>`;
  } else {
    modalErrors.innerHTML = '';
  }

  bootstrap.Modal.getOrCreateInstance(document.getElementById('resultModal')).show();
}

function postAction(url, formData) {
  return fetch(url, {
    method: 'POST',
    headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRF-Token': csrfToken },
    body: formData,
  }).then(r => r.json());
}

function buildRejectForm(showCounter) {
  return `
    <form id="rejectForm">
      <div class="mb-3">
        <label for="rejectReason" class="form-label">Rejection Comments (max 250 characters)</label>
        <textarea class="form-control" id="rejectReason" name="rejectReason" rows="4" maxlength="250" placeholder="Enter rejection comments..."></textarea>
        ${showCounter ? '<small id="rejectReasonCount" class="form-text text-muted">0/250 characters</small>' : ''}
      </div>
    </form>
  `;
}

document.addEventListener('DOMContentLoaded', function () {
  // Shared modal element references
  const rejectModal          = document.getElementById('rejectModal');
  const rejectModalBody      = document.getElementById('rejectModalBody');
  const rejectConfirmBtn     = document.getElementById('rejectConfirmBtn');
  const photoModal           = document.getElementById('photoModal');
  const photoModalBody       = document.getElementById('photoModalBody');
  const resultModal          = document.getElementById('resultModal');
  const commentsModal        = document.getElementById('commentsModal');
  const commentsModalBody    = document.getElementById('commentsModalBody');
  const createAdminModal     = document.getElementById('createAdminModal');
  const createAdminModalBody = document.getElementById('createAdminModalBody');
  const editAdminModal       = document.getElementById('editAdminModal');
  const editAdminModalBody   = document.getElementById('editAdminModalBody');
  const deleteAdminModal     = document.getElementById('deleteAdminModal');
  const deleteAdminModalBody = document.getElementById('deleteAdminModalBody');
  const deleteSubmissionModal     = document.getElementById('deleteSubmissionModal');
  const deleteSubmissionModalBody = document.getElementById('deleteSubmissionModalBody');

  // ── Select-all / row highlight / button toggle ────────────────────────────

  const selectAll   = document.getElementById('selectAllPending');
  const checkboxes  = document.querySelectorAll('.pending-checkbox');
  const cbRows      = Array.from(checkboxes).map(cb => cb.closest('tr'));
  const actionsHeader = document.querySelector('thead th:last-child');

  function updateRowHighlight() {
    checkboxes.forEach((cb, i) => {
      cbRows[i]?.classList.toggle('table-active', cb.checked);
    });
  }

  function toggleRowButtons() {
    const anySelected = Array.from(checkboxes).some(cb => cb.checked);
    document.querySelectorAll('tbody tr').forEach(row => {
      const approveBtn = row.querySelector('.btn-success[data-request-id]');
      const rejectBtn  = row.querySelector('.btn-danger[data-request-id]');
      if (approveBtn && rejectBtn) {
        approveBtn.style.display = anySelected ? 'none' : '';
        rejectBtn.style.display  = anySelected ? 'none' : '';
      }
    });
    if (actionsHeader) actionsHeader.style.display = anySelected ? 'none' : '';
  }

  if (selectAll) {
    selectAll.addEventListener('change', function () {
      checkboxes.forEach(cb => { cb.checked = selectAll.checked; });
      updateRowHighlight();
      toggleRowButtons();
    });
  }
  checkboxes.forEach(cb => {
    cb.addEventListener('change', () => { updateRowHighlight(); toggleRowButtons(); });
  });

  // ── Bulk approve ─────────────────────────────────────────────────────────

  const approveSelectedBtn = document.getElementById('approveSelectedBtn');
  if (approveSelectedBtn) {
    approveSelectedBtn.addEventListener('click', function (e) {
      e.preventDefault();
      const ids = Array.from(document.querySelectorAll('.pending-checkbox:checked')).map(cb => cb.value);
      if (!ids.length) { alert('No requests selected.'); return; }
      const formData = new FormData();
      formData.append('action', 'approve');
      ids.forEach(id => formData.append('request_ids', id));
      postAction(batchEditUrl, formData)
        .then(data => showResultModal(data.success, data.message, data.errors || {}))
        .catch(() => showResultModal(false, 'An error occurred while approving the submissions.'));
    });
  }

  // ── Bulk reject ──────────────────────────────────────────────────────────

  const rejectSelectedBtn = document.getElementById('rejectSelectedBtn');
  if (rejectSelectedBtn) {
    rejectSelectedBtn.addEventListener('click', function (e) {
      e.preventDefault();
      const ids = Array.from(document.querySelectorAll('.pending-checkbox:checked')).map(cb => cb.value);
      if (!ids.length) { alert('No requests selected.'); return; }
      rejectModalBody.innerHTML = buildRejectForm(false);
      const modalInstance = bootstrap.Modal.getOrCreateInstance(rejectModal);
      modalInstance.show();
      rejectConfirmBtn.onclick = function () {
        const comments = document.getElementById('rejectReason').value.trim();
        if (!comments) { alert('Please enter rejection comments.'); return; }
        const formData = new FormData();
        formData.append('action', 'reject');
        ids.forEach(id => formData.append('request_ids', id));
        formData.append('comments', comments);
        postAction(batchEditUrl, formData)
          .then(data => showResultModal(data.success, data.message, data.errors || {}))
          .catch(() => showResultModal(false, 'An error occurred while rejecting the submissions.'))
          .finally(() => modalInstance.hide());
      };
    });
  }

  // ── Single approve ───────────────────────────────────────────────────────

  document.querySelectorAll('.btn-success[data-request-id]').forEach(button => {
    button.addEventListener('click', function () {
      const formData = new FormData();
      formData.append('request_id', this.getAttribute('data-request-id'));
      postAction(approveUrl, formData)
        .then(data => showResultModal(data.success, data.message, data.errors || {}))
        .catch(() => showResultModal(false, 'An error occurred while approving the submission.'));
    });
  });

  // ── Single reject ────────────────────────────────────────────────────────

  document.querySelectorAll('.btn-danger[data-action="reject"]').forEach(button => {
    button.addEventListener('click', function () {
      const requestId = this.getAttribute('data-request-id');
      rejectModalBody.innerHTML = buildRejectForm(true);
      const modalInstance = bootstrap.Modal.getOrCreateInstance(rejectModal);
      modalInstance.show();
      const rejectReasonInput = document.getElementById('rejectReason');
      const rejectReasonCount = document.getElementById('rejectReasonCount');
      rejectReasonInput.addEventListener('input', function () {
        rejectReasonCount.textContent = `${rejectReasonInput.value.length}/250 characters`;
      });
      rejectConfirmBtn.onclick = function () {
        const comments = rejectReasonInput.value.trim();
        if (!comments) { alert('Please enter rejection comments.'); return; }
        const formData = new FormData();
        formData.append('request_id', requestId);
        formData.append('comments', comments);
        postAction(rejectUrl, formData)
          .then(data => showResultModal(data.success, data.message, data.errors || {}))
          .catch(() => showResultModal(false, 'An error occurred while rejecting the submission.'))
          .finally(() => modalInstance.hide());
      };
    });
  });

  // ── Photo modal ──────────────────────────────────────────────────────────

  if (photoModal) {
    photoModal.addEventListener('show.bs.modal', function (event) {
      const btn = event.relatedTarget;
      photoModalBody.innerHTML = `
        <div class="mb-3 text-center">
          <div class="fw-bold mb-1">User Photo</div>
          <img src="${escapeHtml(btn.getAttribute('data-photo-user'))}" alt="User Photo" class="img-fluid d-block mx-auto" style="max-height:200px;">
        </div>
        <div class="text-center">
          <div class="fw-bold mb-1">Driver's License</div>
          <img src="${escapeHtml(btn.getAttribute('data-photo-license'))}" alt="License Photo" class="img-fluid d-block mx-auto" style="max-height:200px;">
        </div>
      `;
    });
  }

  // ── Result modal — reload page on close ──────────────────────────────────

  if (resultModal) {
    resultModal.addEventListener('hide.bs.modal', function () {
      window.location.reload();
    });
  }

  // ── Comments modal ───────────────────────────────────────────────────────

  document.querySelectorAll('.btn-warning[data-comments]').forEach(button => {
    button.addEventListener('click', function () {
      const label = document.createElement('label');
      label.className = 'form-label';
      label.textContent = 'Rejection Comments';
      const textarea = document.createElement('textarea');
      textarea.className = 'form-control';
      textarea.rows = 4;
      textarea.readOnly = true;
      textarea.textContent = this.getAttribute('data-comments');
      const wrapper = document.createElement('div');
      wrapper.className = 'mb-3';
      wrapper.appendChild(label);
      wrapper.appendChild(textarea);
      commentsModalBody.innerHTML = '';
      commentsModalBody.appendChild(wrapper);
      bootstrap.Modal.getOrCreateInstance(commentsModal).show();
    });
  });

  // ── Create admin modal ───────────────────────────────────────────────────

  const createAdminBtn = document.getElementById('createAdminBtn');
  if (createAdminBtn) {
    createAdminBtn.addEventListener('click', function () {
      const authMode    = _cfg.adminAuthMode;
      const entraOnly   = authMode === 'entra';
      const entraEnabled = authMode === 'entra' || authMode === 'both';
      createAdminModalBody.innerHTML = `
        <form id="createAdminForm" method="POST" action="/create_admin_account">
          <input type="hidden" name="csrf_token" value="${escapeHtml(csrfToken)}">
          ${entraEnabled ? `<div class="alert alert-info d-flex align-items-center gap-2 py-2 mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 21 21"><rect x="1" y="1" width="9" height="9" fill="#f25022"/><rect x="11" y="1" width="9" height="9" fill="#7fba00"/><rect x="1" y="11" width="9" height="9" fill="#00a4ef"/><rect x="11" y="11" width="9" height="9" fill="#ffb900"/></svg>
            ${entraOnly ? 'This admin will sign in with their Microsoft account. Name will be populated on first login.' : 'This admin can sign in with Microsoft or their local credentials.'}
          </div>` : ''}
          ${entraOnly ? '' : `<div class="mb-3">
            <label for="firstName" class="form-label">First Name</label>
            <input type="text" class="form-control" id="firstName" name="first_name" required>
          </div>
          <div class="mb-3">
            <label for="lastName" class="form-label">Last Name</label>
            <input type="text" class="form-control" id="lastName" name="last_name" required>
          </div>
          <div class="mb-3">
            <label for="username" class="form-label">Username</label>
            <input type="text" class="form-control" id="username" name="username" required>
          </div>`}
          <div class="mb-3">
            <label for="email" class="form-label">Email</label>
            <input type="email" class="form-control" id="email" name="email" required>
          </div>
          <div class="mb-3">
            <label for="role" class="form-label">Role</label>
            <select class="form-select" id="role" name="role" required>
              <option value="manager">Manager</option>
              <option value="super">Super</option>
            </select>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-outline-light" data-bs-dismiss="modal">Cancel</button>
            <button type="submit" class="btn btn-primary">Create</button>
          </div>
        </form>
      `;
      bootstrap.Modal.getOrCreateInstance(createAdminModal).show();
    });
  }

  // ── Edit admin modal ─────────────────────────────────────────────────────

  document.querySelectorAll('.editAdminBtn[data-admin]').forEach(button => {
    button.addEventListener('click', function () {
      const admin     = JSON.parse(this.getAttribute('data-admin'));
      const nameParts = (admin.full_name || '').split(' ').filter(Boolean);
      const firstName = nameParts[0] || '';
      const lastName  = nameParts.slice(1).join(' ') || '';
      editAdminModalBody.innerHTML = `
        <form id="createAdminForm" method="POST" action="/edit_admin_account">
          <input type="hidden" name="user_id" value="${escapeHtml(admin.id)}">
          <input type="hidden" name="csrf_token" value="${escapeHtml(csrfToken)}">
          <div class="mb-3">
            <label for="firstName" class="form-label">First Name</label>
            <input type="text" class="form-control" id="firstName" name="first_name" value="${escapeHtml(firstName)}" required>
          </div>
          <div class="mb-3">
            <label for="lastName" class="form-label">Last Name</label>
            <input type="text" class="form-control" id="lastName" name="last_name" value="${escapeHtml(lastName)}" required>
          </div>
          <div class="mb-3">
            <label for="username" class="form-label">Username</label>
            <input type="text" class="form-control" id="username" name="username" value="${escapeHtml(admin.username)}" required>
          </div>
          <div class="mb-3">
            <label for="email" class="form-label">Email</label>
            <input type="email" class="form-control" id="email" name="email" value="${escapeHtml(admin.email)}" required>
          </div>
          <div class="mb-3">
            <label for="role" class="form-label">Role</label>
            <select class="form-select" id="role" name="role" required>
              <option value="manager" ${admin.role === 'manager' ? 'selected' : ''}>Manager</option>
              <option value="super" ${admin.role === 'super' ? 'selected' : ''}>Super</option>
            </select>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-outline-light" data-bs-dismiss="modal">Cancel</button>
            <button type="submit" class="btn btn-primary">Update</button>
          </div>
        </form>
      `;
      bootstrap.Modal.getOrCreateInstance(editAdminModal).show();
    });
  });

  // ── Delete admin modal ───────────────────────────────────────────────────

  document.querySelectorAll('.deleteAdminBtn[data-admin]').forEach(button => {
    button.addEventListener('click', function () {
      const admin = JSON.parse(this.getAttribute('data-admin'));
      deleteAdminModalBody.innerHTML = `
        <p>Are you sure you want to delete admin <strong>${escapeHtml(admin.full_name || admin.username)}</strong>?</p>
        <input type="hidden" id="deleteAdminUserId" value="${escapeHtml(admin.id)}">
        <div class="modal-footer">
          <button type="button" class="btn btn-outline-light" data-bs-dismiss="modal">No</button>
          <button type="button" class="btn btn-danger" id="confirmDeleteAdminBtn">Yes, Delete</button>
        </div>
      `;
      const modalInstance = bootstrap.Modal.getOrCreateInstance(deleteAdminModal);
      modalInstance.show();
      document.getElementById('confirmDeleteAdminBtn').onclick = function () {
        const formData = new FormData();
        formData.append('user_id', document.getElementById('deleteAdminUserId').value);
        postAction('/delete_admin_account', formData)
          .then(data => showResultModal(data.success, data.message || (data.success ? 'Admin deleted successfully.' : 'Failed to delete admin.')))
          .catch(() => showResultModal(false, 'An error occurred while deleting the admin.'))
          .finally(() => modalInstance.hide());
      };
    });
  });

  // ── Delete submission modal ──────────────────────────────────────────────

  document.querySelectorAll('.deleteSubmissionBtn[data-request-id]').forEach(button => {
    button.addEventListener('click', function () {
      const requestId = this.getAttribute('data-request-id');
      const name      = this.getAttribute('data-submission');
      deleteSubmissionModalBody.innerHTML = `
        <form id="deleteSubmission">
          <div class="mb-3">
            <p>Are you sure you would like to delete this submission for <b>${escapeHtml(name)}</b>?</p>
          </div>
        </form>
      `;
      const modalInstance = bootstrap.Modal.getOrCreateInstance(deleteSubmissionModal);
      modalInstance.show();
      document.getElementById('deleteConfirmBtn').onclick = function () {
        const formData = new FormData();
        formData.append('request_id', requestId);
        postAction(deleteUrl, formData)
          .then(data => showResultModal(data.success, data.message, data.errors || {}))
          .catch(() => showResultModal(false, 'An error occurred while deleting the submission.'))
          .finally(() => modalInstance.hide());
      };
    });
  });
});
