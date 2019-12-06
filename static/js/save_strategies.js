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
    var strategyCheckboxes = $('.str');
    var submitStrategyButton = $('#save-str');
    var account = $('#account_id').attr('value');
    var user = $('#user_logged').attr('data-user');
    var userList = parseInt(user);
    var campaignForm = $('form#strategy_select');

    console.log(strategyCheckboxes);
    console.log(submitStrategyButton);
    console.log(account);
    console.log(user);
    console.log(userList);

    campaignForm.submit(false);


    $(submitStrategyButton).on('click', function(){

        strategyCheckboxes.each(function (index, element) {
            if ($(this).is(':checked') && !($(this).is(':disabled'))) {
                var strategyId = $(this).attr('value');
                var strategyName = $(this).attr('id');

                $.ajax({
                    url: "../../api/strategies/",
                    data: {
                        "name": strategyName,
                        "strategy_id": parseInt(strategyId),
                        "account": parseInt(account),
                        "user": userList,
                    },
                    type: "POST",
                }).done(function(result) { console.log(result)
                }).fail(function(xhr,status,err) { console.log(err)
                }).always(function(xhr,status) { console.log(status)
                });
            } else {
                console.log("Strategia nie zaznaczona - pomijam dodawanie")
            }
        });

        window.location.replace("../../");
    });
});
