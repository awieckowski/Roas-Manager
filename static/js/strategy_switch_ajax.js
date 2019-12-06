function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
var csrftoken = getCookie('csrftoken');

function csrfSafeMethod(method) {
    // these HTTP methods do not require CSRF protection
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}
$.ajaxSetup({
    beforeSend: function(xhr, settings) {
        if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
            xhr.setRequestHeader("X-CSRFToken", csrftoken);
        }
    }
});

$(function(){
        var switches = $('.ajax-switch');
    switches.each(function (index, element) {
        var strategyId = $(this).attr('id');
        if ($(this).prop("checked") == true) {
            var targetValue = false
        } else {
            targetValue = true
        }
        $(this).on('click', function(){
            $.ajax({
                url: "../api/strategies/" + strategyId + "/",
                data: {
                    "id": strategyId,
                    "make_changes": targetValue
                },
                type: "PATCH",
            }).done(function(result) { console.log(result)
            }).fail(function(xhr,status,err) { console.log(err)
            }).always(function(xhr,status) { console.log(status)
            });
        });
    });
});