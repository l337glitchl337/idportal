document.addEventListener('DOMContentLoaded', function () {

  function setBulkRequestIds(ids) {
    const container = document.getElementById('bulkRequestIdsContainer');
    container.innerHTML = '';
    ids.forEach(function (id) {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'request_ids';
      input.value = id;
      container.appendChild(input);
    });
  }

  function showResultModal(success, message, errors = {}) {
    const modalTitle = document.getElementById('resultModalTitle');
    const modalBody = document.getElementById('resultModalBody');
    const modalErrors = document.getElementById('resultModalErrors');

    if (!modalTitle || !modalBody || !modalErrors) {
      console.error("Modal elements not found in the DOM.");
      return;
    }

    // Update modal title and message
    modalTitle.textContent = success ? "Success" : "Error";
    modalBody.innerHTML = message;

    // Update modal errors if any
    if (Object.keys(errors).length > 0) {
      const errorList = Object.entries(errors)
        .map(([id, error]) => `<li>Request ID ${id}: ${error}</li>`)
        .join('');
      modalErrors.innerHTML = `<ul>${errorList}</ul>`;
    } else {
      modalErrors.innerHTML = ''; // Clear errors if none
    }

    // Show the modal
    bootstrap.Modal.getOrCreateInstance(document.getElementById('resultModal')).show();
  }

  // Approve Selected
  document.getElementById('approveSelectedBtn').addEventListener('click', function (e) {
    e.preventDefault();
    const ids = Array.from(document.querySelectorAll('.pending-checkbox:checked')).map(cb => cb.value);
    if (ids.length === 0) {
      alert('No requests selected.');
      return;
    }

    const formData = new FormData();
    formData.append('action', 'approve');
    ids.forEach(id => formData.append('request_ids', id));

    fetch(batchEditUrl, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      body: formData
    })
      .then(response => response.json())
      .then(data => {
        showResultModal(data.success, data.message, data.errors || {});
      })
      .catch(() => {
        showResultModal(false, 'An error occurred while approving the submissions.');
      });
  });

  // Reject Selected
  document.getElementById('rejectSelectedBtn').addEventListener('click', function (e) {
    e.preventDefault();
    const ids = Array.from(document.querySelectorAll('.pending-checkbox:checked')).map(cb => cb.value);
    if (ids.length === 0) {
      alert('No requests selected.');
      return;
    }

    // Populate the modal body with the rejection comments text box
    rejectModalBody.innerHTML = `
      <form id="rejectForm">
        <div class="mb-3">
          <label for="rejectReason" class="form-label">Rejection Comments (max 250 characters)</label>
          <textarea class="form-control" id="rejectReason" name="rejectReason" rows="4" maxlength="250" placeholder="Enter rejection comments..."></textarea>
        </div>
      </form>
    `;

    // Show the modal
    const modalInstance = bootstrap.Modal.getOrCreateInstance(rejectModal);
    modalInstance.show();

    // Handle confirmation
    rejectConfirmBtn.onclick = function () {
      const rejectReasonInput = document.getElementById('rejectReason');
      const comments = rejectReasonInput.value.trim();
      if (comments.length === 0) {
        alert('Please enter rejection comments.');
        return;
      }

      const formData = new FormData();
      formData.append('action', 'reject');
      ids.forEach(id => formData.append('request_ids', id));
      formData.append('comments', comments);

      fetch(batchEditUrl, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        body: formData
      })
        .then(response => response.json())
        .then(data => {
          showResultModal(data.success, data.message, data.errors || {});
          modalInstance.hide(); // Close the modal after submission
        })
        .catch(() => {
          showResultModal(false, 'An error occurred while rejecting the submissions.');
          modalInstance.hide(); // Close the modal after submission
        });
    };
  });

  // Approve Single Submission
  document.querySelectorAll('.btn-success[data-request-id]').forEach(button => {
    button.addEventListener('click', function () {
      const requestId = this.getAttribute('data-request-id'); // Get the request ID from the button
      const formData = new FormData();
      formData.append('request_id', requestId);

      fetch(approveUrl, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        body: formData
      })
        .then(response => response.json())
        .then(data => {
          showResultModal(data.success, data.message, data.errors || {});
        })
        .catch(() => {
          showResultModal(false, 'An error occurred while approving the submission.');
        });
    });
  });

  // Reject Single Submission
  document.querySelectorAll('.btn-danger[data-request-id]').forEach(button => {
    button.addEventListener('click', function () {
      const requestId = this.getAttribute('data-request-id'); // Get the request ID from the button

      // Populate the modal body with the rejection comments text box and live character count
      const rejectModal = document.getElementById('rejectModal');
      const rejectModalBody = document.getElementById('rejectModalBody');
      const rejectConfirmBtn = document.getElementById('rejectConfirmBtn');

      rejectModalBody.innerHTML = `
        <form id="rejectForm">
          <div class="mb-3">
            <label for="rejectReason" class="form-label">Rejection Comments (max 250 characters)</label>
            <textarea class="form-control" id="rejectReason" name="rejectReason" rows="4" maxlength="250" placeholder="Enter rejection comments..."></textarea>
            <small id="rejectReasonCount" class="form-text text-muted">0/250 characters</small>
          </div>
        </form>
      `;

      // Show the modal
      const modalInstance = bootstrap.Modal.getOrCreateInstance(rejectModal);
      modalInstance.show();

      // Handle live character count
      const rejectReasonInput = document.getElementById('rejectReason');
      const rejectReasonCount = document.getElementById('rejectReasonCount');

      rejectReasonInput.addEventListener('input', function () {
        const currentLength = rejectReasonInput.value.length;
        rejectReasonCount.textContent = `${currentLength}/250 characters`;
      });

      // Handle confirmation
      rejectConfirmBtn.onclick = function () {
        const comments = rejectReasonInput.value.trim();
        if (comments.length === 0) {
          alert('Please enter rejection comments.');
          return;
        }

        const formData = new FormData();
        formData.append('request_id', requestId);
        formData.append('comments', comments);

        fetch(rejectUrl, {
          method: 'POST',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
          body: formData
        })
          .then(response => response.json())
          .then(data => {
            showResultModal(data.success, data.message, data.errors || {});
            modalInstance.hide(); // Close the modal after submission
          })
          .catch(() => {
            showResultModal(false, 'An error occurred while rejecting the submission.');
            modalInstance.hide(); // Close the modal after submission
          });
      };
    });
  });
});

document.addEventListener('DOMContentLoaded', function () {
    const photoModal = document.getElementById('photoModal');
    const photoModalBody = document.getElementById('photoModalBody');

    photoModal.addEventListener('show.bs.modal', function (event) {
        const button = event.relatedTarget; // Button that triggered the modal
        const userPhotoUrl = button.getAttribute('data-photo-user');
        const licensePhotoUrl = button.getAttribute('data-photo-license');

        // Update the modal body with the photos, centered
        photoModalBody.innerHTML = `
            <div class="mb-3 text-center">
                <div class="fw-bold mb-1">User Photo</div>
                <img src="${userPhotoUrl}" alt="User Photo" class="img-fluid d-block mx-auto" style="max-height:200px;">
            </div>
            <div class="text-center">
                <div class="fw-bold mb-1">Driver's License</div>
                <img src="${licensePhotoUrl}" alt="License Photo" class="img-fluid d-block mx-auto" style="max-height:200px;">
            </div>
        `;
    });
});

document.addEventListener('DOMContentLoaded', function() {
    const selectAll = document.getElementById('selectAllPending');
    const checkboxes = document.querySelectorAll('.pending-checkbox');
    const rows = Array.from(checkboxes).map(cb => cb.closest('tr'));

    function updateRowHighlight() {
      checkboxes.forEach((cb, i) => {
        if (cb.checked) {
          rows[i].classList.add('table-active');
        } else {
          rows[i].classList.remove('table-active');
        }
      });
    }

    if (selectAll) {
      selectAll.addEventListener('change', function() {
        checkboxes.forEach(cb => { cb.checked = selectAll.checked; });
        updateRowHighlight();
      });
    }

    checkboxes.forEach((cb, i) => {
      cb.addEventListener('change', updateRowHighlight);
    });
});

document.addEventListener('DOMContentLoaded', function () {
  const resultModal = document.getElementById('resultModal');

  if (resultModal) {
    resultModal.addEventListener('hide.bs.modal', function () {
      // Refresh the current page
      window.location.reload();
    });
  }
});

document.addEventListener('DOMContentLoaded', function () {
  const commentsModal = document.getElementById('commentsModal');
  const commentsModalBody = document.getElementById('commentsModalBody');

  // Handle "View Comments" button click
  document.querySelectorAll('.btn-warning[data-comments]').forEach(button => {
    button.addEventListener('click', function () {
      const comments = this.getAttribute('data-comments'); // Get the comments from the button's data attribute

      // Populate the modal body with the comments
      commentsModalBody.innerHTML = `
        <div class="mb-3">
          <label class="form-label">Rejection Comments</label>
          <textarea class="form-control" rows="4" readonly>${comments}</textarea>
        </div>
      `;

      // Show the modal
      const modalInstance = bootstrap.Modal.getOrCreateInstance(commentsModal);
      modalInstance.show();
    });
  });
});

document.addEventListener('DOMContentLoaded', function () {
  const checkboxes = document.querySelectorAll('.pending-checkbox');
  const rows = document.querySelectorAll('tbody tr');
  const actionsHeader = document.querySelector('thead th:last-child'); // Select the "Actions" header

  function toggleRowButtons() {
    const anySelected = Array.from(checkboxes).some(checkbox => checkbox.checked);

    rows.forEach(row => {
      const approveButton = row.querySelector('.btn-success[data-request-id]');
      const rejectButton = row.querySelector('.btn-danger[data-request-id]');

      if (approveButton && rejectButton) {
        approveButton.style.display = anySelected ? 'none' : '';
        rejectButton.style.display = anySelected ? 'none' : '';
      }
    });

    // Toggle visibility of the "Actions" header
    if (actionsHeader) {
      actionsHeader.style.display = anySelected ? 'none' : '';
    }
  }

  // Add event listeners to checkboxes
  checkboxes.forEach(checkbox => {
    checkbox.addEventListener('change', toggleRowButtons);
  });

  // Add event listener to "Select All" checkbox
  const selectAllCheckbox = document.getElementById('selectAllPending');
  if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener('change', function () {
      checkboxes.forEach(checkbox => {
        checkbox.checked = selectAllCheckbox.checked;
      });
      toggleRowButtons();
    });
  }
});

document.addEventListener('DOMContentLoaded', function () {
  const createAdminModal = document.getElementById('createAdminModal');
  const createAdminModalBody = document.getElementById('createAdminModalBody');

  // Open Create Admin Modal
  document.getElementById('createAdminBtn').addEventListener('click', function () {
    // Populate the modal body with a form
    createAdminModalBody.innerHTML = `
      <form id="createAdminForm" method="POST" action="/create_admin_account">
        <div class="mb-3">
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
        </div>
        <div class="mb-3">
          <label for="email" class="form-label">Email</label>
          <input type="email" class="form-control" id="email" name="email" required>
        </div>
        <div class="mb-3">
          <label for="password" class="form-label">Password</label>
          <input type="password" class="form-control" id="password" name="password" required>
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

    // Show the modal
    const modalInstance = bootstrap.Modal.getOrCreateInstance(createAdminModal);
    modalInstance.show();
  });
});