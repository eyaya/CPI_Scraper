const responsive = {
    0: {
        items: 1
    },
    320: {
        items: 1
    },
    560: {
        items: 2
    },
    960: {
        items: 3
    }
}

$(document).ready(function() {
    $(" a").filter(function() {
        return this.href == location.href.replace(/#.*/, "");
    }).addClass("active");
    $(".navbar-nav li a").click(function(event) {
        // check if window is small enough so dropdown is created
        var toggle = $(".navbar-toggle").is(":visible");
        if (toggle) {
            $(".navbar-collapse").collapse('hide');
        }
    });
    // Hero slider JS
    $('.hero-slider').owlCarousel({

        loop: true,
        autoplay: true,
        autoplayTimeout: 4000,
        items: 1,
        nav: true,
        dots: true,
    })

    /*  owl-carousel blog*/
    $('.owl-carousel').owlCarousel({
        loop: true,
        autoplay: true,
        autoplayTimeout: 3000,
        dots: false,
        nav: true,
        navText: [$('.owl-navigation .owl-nav-prev'), $('.owl-navigation .owl-nav-next')],
        responsive: responsive,
    });
    // click to scroll top 
    $('.move-up span').click(function() {
        $('html,body').animate({
            scrollTop: 0
        }, 1000);
    })

    // animation on scroll Instance
    AOS.init();


    CKEDITOR.editorConfig = function(config) {
        // Other configs
        config.filebrowserImageBrowseUrl = '/ckeditor/pictures';
        config.filebrowserImageUploadUrl = '/ckeditor/pictures';

    };
    $('#myCarousel').carousel({
        interval: 3000,
    })
})