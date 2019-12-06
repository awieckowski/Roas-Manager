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
    var campaignGroupCheckboxes = $('.cg');
    var submitCampaignGroupButton = $('#save-cg');
    var account = $('#account_id').attr('value');
    var user = $('#user_logged').attr('data-user');
    var userInt = parseInt(user);


    console.log(campaignGroupCheckboxes);
    console.log(submitCampaignGroupButton);
    console.log(account);

    $(submitCampaignGroupButton).click(function(event) {
        event.preventDefault();
    });

    $(submitCampaignGroupButton).on('click', function(){

        campaignGroupCheckboxes.each(function (index, element) {
            if ($(this).is(':checked') && !($(this).is(':disabled'))) {
                var campaignGroupId = $(this).attr('value');
                var campaignGroupName = $(this).attr('id');

                $.ajax({
                    url: "../../api/campaign-groups/",
                    data: {
                        "name": campaignGroupName,
                        "campaign_group_id": parseInt(campaignGroupId),
                        "account": parseInt(account),
                        "user": userInt
                    },
                    type: "POST",
                }).done(function(result) { console.log(result)
                }).fail(function(xhr,status,err) { console.log(err)
                }).always(function(xhr,status) { console.log(status)
                });
            } else {
                console.log("Grupa kampanii nie zaznaczona - pomijam dodawanie")
            }
        });

        window.location.replace("../");
    });
});
