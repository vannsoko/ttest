CTFd._internal.challenge.data = undefined;

CTFd._internal.challenge.renderer = null;

CTFd._internal.challenge.preRender = function () { };

CTFd._internal.challenge.render = null;

CTFd._internal.challenge.postRender = function () {
  loadInstanceInfo();
};

function loadInstanceInfo() {
  setTimeout(() => {
    $('#instancer-panel-loading').hide();
    $('#instancer-panel-stopped').show();
  }, 5);
}

if (window.$ === undefined) window.$ = CTFd.lib.$;

CTFd._internal.challenge.submit = function (preview) {
  var challenge_id = parseInt(CTFd.lib.$("#challenge-id").val());
  var submission = CTFd.lib.$("#challenge-input").val();

  var body = {
    challenge_id: challenge_id,
    submission: submission
  };
  var params = {};
  if (preview) {
    params["preview"] = true;
  }

  return CTFd.api.post_challenge_attempt(params, body).then(function (response) {
    if (response.status === 429) {
      // User was ratelimited but process response
      return response;
    }
    if (response.status === 403) {
      // User is not logged in or CTF is paused.
      return response;
    }
    return response;
  });
};

CTFd._internal.challenge.spawn = function () {
  console.log("Spawn has been pressed!");
  $('#instancer-spawn-spinner').show();
  setTimeout(() => {
    $('#instancer-panel-stopped').hide();
    $('#instancer-panel-running').show();
  }, 1500);
}
CTFd._internal.challenge.renew = function () {
  console.log("Renew has been pressed!");
}
CTFd._internal.challenge.restart = function () {
  console.log("Restart has been pressed!");
}
CTFd._internal.challenge.destroy = function () {
  console.log("Destroy has been pressed!");
  setTimeout(() => $('#instancer-destroy-spinner').show(), 5);
}
CTFd._internal.challenge.copy_instance_url = function () {
  const url = $('#instancer-url').text();
  navigator.clipboard.writeText(url).then(() => {
    const $btn = $('#instancer-url').next('button');
    $btn.html('<i class="fa-solid fa-check"></i>');
    setTimeout(() => $btn.html('<i class="fa-regular fa-copy"></i>'), 1500);
  });
}
