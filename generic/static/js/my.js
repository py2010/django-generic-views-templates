

function DeleteObj(that, id, url) {

    if (! url) {
        url = window.location.pathname.replace(/(\/$)/g,'') + '/delete/';
    }
    console.log(that);

    swal({
        title: '确定删除此条数据？',
        // text: "",
        type: "warning",
        showCancelButton: true,
        cancelButtonText: '取消',
        confirmButtonText: '确定',
        confirmButtonColor: "#ed5565",

    })
    .then((result) => {
        if (result.value) {

            var data;
            if (id) {
                data = 'id=' + id
            } else if (that.text=='删除') {
                data = 'id=' + that.parentNode.parentNode.id || that.parentNode.id;
            } else if (that.text=='批量删除') {
                data = $('#list_object_form').serialize();
            } else {
                swal('出错', '未知的操作类型: "'+that.text+'"', "error");
                return false;
            }

            console.log(data);
            $.ajax({
                url: url,
                type: 'POST',
                data: data,
                success: function (res) {
                    // console.log(res);
                    if (res.status) {
                        swal({ 
                            title: "删除成功",
                            type: 'success',
                            position: 'top',
                            timer: 3000,
                            toast: true,
                            showConfirmButton: false
                        })
                        setTimeout('location.reload()', 2000);
                    } else {
                        swal('删除出错', res.error, "error");
                    }
                },
                error: function(error){
                    console.log(error)
                    swal('删除失败', "HTTP: " + error.status, "error");
                },

            })


        }

    });

}


// function getUrlParam(name) {
//     //解析当前URL参数，getUrlParam(参数名)
//     var reg = new RegExp("(^|&)" + name + "=([^&]*)(&|$)"); 
//     var locationHref = decodeURIComponent(window.location.search);
//     var r = locationHref.substr(1).match(reg);
//     if(r != null) {
//         if(unescape){
//             return unescape(r[2]);
//         }else{
//             return r[2];
//         }
//     }else{
//         return null;
//     }
// }
