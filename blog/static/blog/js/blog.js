(function () {
  'use strict';

  // Like / unlike without a page reload. Falls back to a normal form POST without JS.
  var likeForm = document.querySelector('[data-like-form]');
  if (likeForm) {
    likeForm.addEventListener('submit', function (event) {
      event.preventDefault();
      var btn = likeForm.querySelector('[data-like-btn]');
      if (btn.disabled) return;
      btn.disabled = true;

      fetch(likeForm.action, {
        method: 'POST',
        headers: {
          'X-CSRFToken': likeForm.querySelector('[name="csrfmiddlewaretoken"]').value,
          'X-Requested-With': 'XMLHttpRequest'
        },
        credentials: 'same-origin'
      })
        .then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.json();
        })
        .then(function (data) {
          btn.classList.toggle('is-liked', data.liked);
          btn.setAttribute('aria-pressed', data.liked ? 'true' : 'false');
          likeForm.querySelector('[data-like-icon]').className = 'bi ' + (data.liked ? 'bi-heart-fill' : 'bi-heart');
          likeForm.querySelector('[data-like-label]').textContent = data.liked ? 'Liked' : 'Like';
          likeForm.querySelector('[data-like-count]').textContent = data.count;
        })
        .catch(function () {
          likeForm.submit(); // let the server handle it the non-JS way
        })
        .finally(function () {
          btn.disabled = false;
        });
    });
  }

  // Comment form: live character count and no double submissions.
  var commentForm = document.querySelector('[data-comment-form]');
  if (commentForm) {
    var body = commentForm.querySelector('textarea');
    var counter = commentForm.querySelector('[data-char-count]');
    var update = function () { counter.textContent = body.value.length; };
    if (body && counter) {
      body.addEventListener('input', update);
      update();
    }
    commentForm.addEventListener('submit', function () {
      var submit = commentForm.querySelector('[data-submit-btn]');
      submit.disabled = true;
      submit.textContent = 'Sending…';
    });
  }
})();
