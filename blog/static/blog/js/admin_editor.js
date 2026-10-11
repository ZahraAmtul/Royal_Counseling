/*
 * Image uploads for the blog editor (TinyMCE) in Django Admin.
 * Called by the `images_upload_handler` option set in blog/admin.py.
 * Sends Django's CSRF token from the admin form, so CSRF protection stays on.
 */
window.blogUploadImage = function (blobInfo, progress, uploadUrl) {
  return new Promise(function (resolve, reject) {
    var tokenInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    var xhr = new XMLHttpRequest();
    xhr.open('POST', uploadUrl);
    xhr.setRequestHeader('X-CSRFToken', tokenInput ? tokenInput.value : '');
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');

    xhr.upload.onprogress = function (e) {
      if (e.lengthComputable) progress((e.loaded / e.total) * 100);
    };
    xhr.onload = function () {
      var data = {};
      try { data = JSON.parse(xhr.responseText); } catch (err) { /* not JSON */ }
      if (xhr.status === 200 && data.location) {
        resolve(data.location);
      } else {
        reject({ message: data.error || ('Image upload failed (HTTP ' + xhr.status + ').'), remove: true });
      }
    };
    xhr.onerror = function () {
      reject({ message: 'Image upload failed. Check your connection and try again.', remove: true });
    };

    var formData = new FormData();
    formData.append('file', blobInfo.blob(), blobInfo.filename());
    xhr.send(formData);
  });
};
