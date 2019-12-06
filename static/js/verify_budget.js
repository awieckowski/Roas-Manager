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
    var approvalSelects = $('.verify-budget');
    var saveButton = $('#save');

    $(saveButton).on('click', function(){
        approvalSelects.each(function (index, element) {
            var id = $(this).attr('data-budgetId');
            var verified = $(this).val();
            console.log(parseInt(verified));
            console.log(parseInt(id));
            $.ajax({
                url: "../../api/budgets/" + parseInt(id) + '/',
                data: {
                    "verified": parseInt(verified),
                },
                type: "PATCH",
            }).done(function(result) { console.log(result)
            }).fail(function(xhr,status,err) { console.log(err)
            }).always(function(xhr,status) { console.log(status)
            });
        });
    window.setTimeout(function(){window.location.reload()}, 300);
    });

});


