(function(define) {
    define([
        'underscore',
        'backbone',
        'js/discovery/models/course_card',
        'js/discovery/models/facet_option'
    ], function(_, Backbone, CourseCard, FacetOption) {
        'use strict';

        function compareCourseData(firstData, secondData) {
            var firstTitle = (firstData.content || {}).display_name || '';
            var secondTitle = (secondData.content || {}).display_name || '';
            var titleComparison = firstTitle.localeCompare(secondTitle, 'ro', {
                sensitivity: 'accent',
                numeric: true
            });

            if (titleComparison !== 0) {
                return titleComparison;
            }

            return String(firstData.id || '').localeCompare(String(secondData.id || ''));
        }

        return Backbone.Model.extend({
            url: '/search/course_discovery/',
            jqhxr: null,

            defaults: {
                totalCount: 0,
                latestCount: 0
            },

            initialize: function() {
                this.courseCards = new Backbone.Collection([], {model: CourseCard});
                this.courseCards.comparator = function(first, second) {
                    return compareCourseData(first.toJSON(), second.toJSON());
                };
                this.facetOptions = new Backbone.Collection([], {model: FacetOption});
                this.latestCourseIds = [];
            },

            parse: function(response) {
                var courses = response.results || [];
                var facets = response.aggs || {};

                courses.sort(function(first, second) {
                    return compareCourseData(first.data || {}, second.data || {});
                });

                var pageCourses = _.pluck(courses, 'data');
                this.latestCourseIds = _.pluck(pageCourses, 'id');
                this.courseCards.add(pageCourses);
                this.courseCards.sort();

                this.set({
                    totalCount: response.total,
                    latestCount: courses.length
                });

                var options = this.facetOptions;
                _(facets).each(function(obj, key) {
                    _(obj.terms).each(function(count, term) {
                        options.add({
                            facet: key,
                            term: term,
                            count: count
                        }, {merge: true});
                    });
                });
            },

            reset: function() {
                this.set({
                    totalCount: 0,
                    latestCount: 0
                });
                this.courseCards.reset();
                this.facetOptions.reset();
                this.latestCourseIds = [];
            },

            latest: function() {
                if (!this.latestCourseIds.length) {
                    return this.courseCards.last(this.get('latestCount'));
                }

                return this.courseCards.filter(function(course) {
                    return this.latestCourseIds.indexOf(course.get('id')) !== -1;
                }, this).sort(this.courseCards.comparator);
            }

        });
    });
}(define || RequireJS.define));
