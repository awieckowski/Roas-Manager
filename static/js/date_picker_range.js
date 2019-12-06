    $(document).ready(function(){
        var date_input1=$('input[name="date_from"]'); //our date input has the name "date"
        var date_input2=$('input[name="date_to"]'); //our date input has the name "date"
        var container=$('.bootstrap-iso form').length>0 ? $('.bootstrap-iso form').parent() : "body";
        var options={
            format: 'yyyy-mm-dd',
            language: "pl",
            container: container,
            todayHighlight: true,
            autoclose: true,
        };
        date_input1.datepicker(options);
        date_input2.datepicker(options);
    });