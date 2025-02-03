(function (define) {
    define([
        'underscore',
        'backbone',
        'js/discovery/models/course_card',
        'js/discovery/models/facet_option'
    ], function (_, Backbone, CourseCard, FacetOption) {
        'use strict';

        return Backbone.Model.extend({
            url: '/search/course_discovery/', // Main course discovery API
            jqhxr: null,

            defaults: {
                totalCount: 0,
                latestCount: 0
            },

            initialize: function () {
                this.courseCards = new Backbone.Collection([], { model: CourseCard });
                this.facetOptions = new Backbone.Collection([], { model: FacetOption });
                this.instructorMap = {}; // Map to store instructor data from the Moochub API

                // Fetch instructor data from the Moochub API
                var self = this;
                $.getJSON('/api/moochub/v1/moochubinfo/')
                    .done(function (response) {
                        response.data.forEach(function (course) {
                            const courseCode = course.attributes.courseCode || course.attributes.id;
                            const instructors = course.attributes.instructor || [];
                            self.instructorMap[courseCode] = instructors.map(i => i.name).join(', ') || 'Instructor: Not Available';
                        });
                        console.log('Instructor map loaded:', self.instructorMap);
                        self.trigger('instructorMap:loaded');
                    })
                    .fail(function () {
                        console.error('Failed to fetch instructor data from Moochub API');
                    });
            },

            parse: function (response) {
                var courses = response.results || [];
                var facets = response.aggs || {};

                // Process courses
                var processedCourses = courses.map(course => {
                    var attributes = course.data;

                    // Match courseCode from the discovery API with the Moochub API's courseCode
                    var courseCode = attributes.number || attributes.id;
                    attributes.instructor_names = this.instructorMap[courseCode] || 'Instructor: Not Available';

                    return attributes;
                });

                this.courseCards.add(processedCourses); // Add processed courses to the course collection

                // Set total and latest counts
                this.set({
                    totalCount: response.total,
                    latestCount: courses.length
                });

                // Process facets
                var options = this.facetOptions;
                _(facets).each(function (obj, key) {
                    _(obj.terms).each(function (count, term) {
                        options.add({
                            facet: key,
                            term: term,
                            count: count
                        }, { merge: true });
                    });
                });
            },

            reset: function () {
                this.set({
                    totalCount: 0,
                    latestCount: 0
                });
                this.courseCards.reset();
                this.facetOptions.reset();
            },

            latest: function () {
                return this.courseCards.last(this.get('latestCount'));
            }
        });
    });
}(define || RequireJS.define));
