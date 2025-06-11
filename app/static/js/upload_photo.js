const idInput     = document.getElementById('idPhotoUpload');
const previewSection = document.getElementById('preview-section');
const previewImage   = document.getElementById('preview');
const cropBtn        = document.getElementById('crop-btn');
const submitBtn      = document.getElementById('submit-btn');
let cropper;
let idCropped = false;
let dlChosen = false;

// Validate file type & size for ID photo
function validateFile(file) {
    const types = ['image/jpeg','image/png','image/webp'];
    return types.includes(file.type) && file.size <= 10*1024*1024;
}

function updateSubmitState() {
    // Show the submit button only if both conditions are met
    if (idCropped && dlChosen) {
    submitBtn.style.display = 'block';
    submitBtn.textContent = 'Submit Documents';
    } else {
    submitBtn.style.display = 'none';
    submitBtn.textContent = '';
    }
}

idInput.addEventListener('change', e => {
    const file = e.target.files[0];
    idCropped = false;
    updateSubmitState();
    if (!file || !validateFile(file)) {
    alert('Please select a JPG/PNG/WEBP under 10 MB.');
    idInput.value = '';
    return;
    }
    const reader = new FileReader();
    reader.onload = evt => {
    previewImage.src = evt.target.result;
    previewSection.style.display = 'block';
    cropBtn.style.display = 'inline-block';

    if (cropper) cropper.destroy();
    cropper = new Cropper(previewImage, {
        aspectRatio: 200 / 200,
        viewMode: 1,
        background: false,
        responsive: true,
        // Fixed crop-box size
        cropBoxResizable: false,
        cropBoxMovable: true,
        minCropBoxWidth: 200,
        minCropBoxHeight: 200,
        maxCropBoxWidth: 200,
        maxCropBoxHeight: 200,
        ready() {
        const cropperInstance = this.cropper;
        const containerData = cropperInstance.getContainerData();
        const left = (containerData.width - 200) / 2;
        const top  = (containerData.height - 200) / 2;
        cropperInstance.setCropBoxData({ left, top, width: 200, height: 200 });
        }
    });
    };
    reader.readAsDataURL(file);
});

cropBtn.addEventListener('click', () => {
    if (!cropper) return;
    const canvas = cropper.getCroppedCanvas({
    width: 300, height: 300, imageSmoothingQuality: 'high'
    });
    canvas.toBlob(blob => {
    const newFile = new File([blob], idInput.files[0].name, { type: blob.type });
    const dt = new DataTransfer();
    dt.items.add(newFile);
    idInput.files = dt.files;

    previewImage.src = URL.createObjectURL(blob);
    cropBtn.style.display = 'none';
    cropper.destroy();
    cropper = null;
    idCropped = true;
    updateSubmitState();
    }, 'image/png');
});

// Driver's License preview
const dlInput = document.getElementById('dlUpload');
const dlPreviewContainer = document.getElementById('dl-preview-container');
const dlPreviewImg = document.getElementById('dl-preview-img');

dlInput.addEventListener('change', e => {
    const file = e.target.files[0];
    dlChosen = false;
    updateSubmitState();
    if (!file) return;
    if (!validateFile(file)) {
    alert('Please select a JPG/PNG/WEBP under 10 MB.');
    dlInput.value = '';
    dlPreviewContainer.style.display = 'none';
    return;
    }
    dlPreviewImg.src = URL.createObjectURL(file);
    dlPreviewContainer.style.display = 'block';
    dlChosen = true;
    updateSubmitState();
});