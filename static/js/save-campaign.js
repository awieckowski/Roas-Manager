function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i].trim();
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
    var campaignsCheckboxes = $('.campaign');
    var submitCampaignButton = $('#save-campaign');
    var account = $('#account_id').attr('value');
    var campaignForm = $('form#campaign_select');
    var user = $('#user_logged').attr('data-user');
    var userInt = parseInt(user);



    campaignForm.submit(false);

    console.log(campaignsCheckboxes);
    console.log(submitCampaignButton);
    console.log(account);
    console.log(user);

    $(submitCampaignButton).on('click', function(){
        campaignsCheckboxes.each(function (index, element) {
            if ($(this).is(':checked') && !($(this).is(':disabled'))) {
                var campaignId = $(this).attr('data-campaign_id');
                var campaignType = $(this).attr('data-campaign_type');
                var campaignName = $(this).attr('value');
                console.log({"x": {
                        "name": campaignName,
                        "type": campaignType,
                        "campaign_id": parseInt(campaignId),
                        "account": parseInt(account),
                        "user": userInt
                    }});
                $.ajax({
                    url: "../../api/campaigns/",
                    data: {
                        "name": campaignName,
                        "type": campaignType,
                        "campaign_id": parseInt(campaignId),
                        "account": parseInt(account),
                    },
                    type: "POST",
                }).done(function(result) { console.log(result)
                }).fail(function(xhr,status,err) { console.log(err)
                }).always(function(xhr,status) { console.log(status)
                });
            } else {
                console.log("Kampania nie zaznaczona - pomijam dodawanie")
            }
        });
        window.location.replace("../");
    });
});
