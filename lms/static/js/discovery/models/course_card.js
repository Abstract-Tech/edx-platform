(function(define) {
    define(['backbone'], function(Backbone) {
        'use strict';

        return Backbone.Model.extend({
            defaults: {
                modes: [],
                course: '',
                enrollment_start: '',
                number: '',
                instructor_names: '',
                content: {
                    overview: '',
                    display_name: '',
                    number: '',
                    instructor_names: '',
                },
                start: '',
                image_url: '',
                org: '',
                id: '',
                instructor_names: '',
            }
        });
    });
}(define || RequireJS.define));
