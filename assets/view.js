// inspired by: ctfd-chall-manager

CTFd._internal.challenge.data = undefined;
CTFd._internal.challenge.renderer = null;
CTFd._internal.challenge.render = null;
if (window.$ === undefined) window.$ = CTFd.lib.$;

CTFd._internal.challenge.preRender = function () { };

CTFd._internal.challenge.postRender = function () {
  load_instance_info();
};

function handle_response(response) {
  if (response.status === 429 || response.status === 403) {
    // User was ratelimited or not logged in or CTF is paused.
    return response.json();
  }
  return response.json();
}


function req_json(method, url) {
  return CTFd.fetch(
    url,
    {
      method: method,
      credentials: 'same-origin',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      },
    }
  ).then(handle_response);
}

function get_req_json(url) {
  return req_json("GET", url);
}
function post_req_json(url) {
  return req_json("POST", url);
}
function delete_req_json(url) {
  return req_json("DELETE", url);
}

function format_count_down(countdown) {
  // Convert
  const seconds = Math.floor((countdown / 1000) % 60);
  const minutes = Math.floor((countdown / (1000 * 60)) % 60);
  const hours = Math.floor((countdown / (1000 * 60 * 60)) % 24);
  const days = Math.floor((countdown / (1000 * 60 * 60 * 24)) % 365);
  // Build str
  var formatted = ""
  if (days > 0) {
    formatted = formatted + days.toString() + "d "
  }
  if (hours > 0) {
    formatted = formatted + hours.toString().padStart(2, '0') + ":"
  }
  if (minutes > 0) {
    formatted = formatted + minutes.toString().padStart(2, '0') + ":"
  }
  formatted = formatted + seconds.toString().padStart(2, '0') + "s";
  return formatted;
}

function loaded_instance_info(instance_data) {
  $('#instancer-panel-loading').hide();
  if (instance_data.running) {
    $('#instancer-panel-running').show();

    if (instance_data.url !== undefined && instance_data.url != "") {
      $('#instancer-url-div').css('visibility', 'visible');
      $('#instancer-url').text(instance_data.url);
    } else {
      $('#instancer-url-div').css('visibility', 'hidden');
    }

    const expires = new Date(instance_data.expires);
    var count_down = expires - new Date();
    if (count_down > 0) {
      $('#instancer-count-down').text(format_count_down(count_down));
      window.count_down_interval_id = setInterval(() => {
        count_down = expires - new Date();
        if (count_down <= 0) {
          load_instance_info();
          return;
        }
        $('#instancer-count-down').text(format_count_down(count_down));
      }, 1000);
    }
  } else {
    $('#instancer-panel-stopped').show();
  }
}

function load_instance_info_cache(challenge_id) {
  const CACHE_VALIDITY = 30000; // 30s
  const cache_key = get_cache_key();
  const instance_cache = JSON.parse(localStorage.getItem(cache_key)) || null;
  if (instance_cache === null) {
    return false;
  }

  if (!instance_cache.receivedAt) {
    return false;
  }
  var valid = new Date() - new Date(instance_cache.received_at) < CACHE_VALIDITY;
  if (!valid) {
    localStorage.removeItem(cache_key);
    return false;
  }

  loaded_instance_info(instance_cache.data);

  return true;
}

function load_instance_info() {
  $('#instancer-panel-loading').show();
  $('#instancer-panel-running').hide();
  $('#instancer-panel-stopped').hide();
  if (window.count_down_interval_id !== undefined) {
    clearInterval(count_down_interval_id);
    window.count_down_interval_id = undefined;
  }
  const challenge_id = CTFd._internal.challenge.data.id;

  if (load_instance_info_cache(challenge_id)) {
    return;
  }

  get_req_json(instance_url()).then((instance_response) => {
    if (instance_response.success) {
      const instance_data = instance_response.data;
      localStorage.setItem(get_cache_key(), JSON.stringify({ data: instance_data, received_at: new Date() }));
      loaded_instance_info(instance_data);
    } else {
      CTFd._functions.events.eventAlert({
        title: "Fail",
        html: instance_response.message
      });
    }
  });

}


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

function instance_url() {
  const challenge_id = CTFd._internal.challenge.data.id;
  return "/api/v1/plugins/instancer-plugin/instance?challengeId=" + challenge_id;
}

function get_cache_key() {
  const challenge_id = CTFd._internal.challenge.data.id;
  const INSTANCE_CACHE_KEY_TEMPLATE = "CTFd:instancer-plugin:instance_";
  return INSTANCE_CACHE_KEY_TEMPLATE + challenge_id;
}

CTFd._internal.challenge.spawn = function () {
  $('#instancer-button-spawn').prop("disabled", true);
  $('#instancer-spawn-spinner').show();

  post_req_json(instance_url()).then((spawn_response) => {
    $('#instancer-spawn-spinner').hide();
    if (spawn_response.success) {
      load_instance_info();
      CTFd._functions.events.eventAlert({
        title: "Success",
        html: "Your instance has been deployed!",
      });
    } else {
      CTFd._functions.events.eventAlert({
        title: "Fail",
        html: spawn_response.message,
      });
    }

  }).finally(() => {
    $('#instancer-button-spawn').prop('disabled', false);
    $('#instancer-spawn-spinner').hide();
  });
}
CTFd._internal.challenge.restart = function () {
  $('#instancer-restart-spinner').show();
  $('#instancer-button-destroy').prop("disabled", true);
  $('#instancer-button-restart').prop("disabled", true);

  delete_req_json(instance_url()).then((destroy_response) => {
    if (destroy_response.success) {
      localStorage.removeItem(get_cache_key());
      post_req_json(instance_url()).then((spawn_response) => {
        if (spawn_response.success) {
          load_instance_info();
          CTFd._functions.events.eventAlert({
            title: "Success",
            html: "Your instance has been restarted!",
          });
        } else {
          CTFd._functions.events.eventAlert({
            title: "Fail",
            html: destroy_response.message,
          });
        }
      });

    } else {
      CTFd._functions.events.eventAlert({
        title: "Fail",
        html: destroy_response.message,
      });
    }
  }).finally(() => {
    $('#instancer-restart-spinner').hide();
    $('#instancer-button-destroy').prop("disabled", false);
    $('#instancer-button-restart').prop("disabled", false);
  });
}
CTFd._internal.challenge.destroy = function () {
  $('#instancer-destroy-spinner').show();
  $('#instancer-button-destroy').prop("disabled", true);
  $('#instancer-button-restart').prop("disabled", true);

  delete_req_json(instance_url()).then((destroy_response) => {
    if (destroy_response.success) {
      localStorage.removeItem(get_cache_key())
      load_instance_info();
      CTFd._functions.events.eventAlert({
        title: "Success",
        html: "Your instance has been destroyed!",
      });
    } else {
      CTFd._functions.events.eventAlert({
        title: "Fail",
        html: destroy_response.message,
      });
    }
  }).finally(() => {
    $('#instancer-destroy-spinner').hide();
    $('#instancer-button-destroy').prop("disabled", false);
    $('#instancer-button-restart').prop("disabled", false);
  });
}
CTFd._internal.challenge.copy_instance_url = function () {
  const url = $('#instancer-url').text();
  navigator.clipboard.writeText(url).then(() => {
    $('#instancer-button-url-copy').html('<i class="fa-solid fa-check"></i>');
    setTimeout(() => $('#instancer-button-url-copy').html('<i class="fa-regular fa-copy"></i>'), 1500);
  });
}
