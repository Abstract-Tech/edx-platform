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
                this.instructorDataLoaded = false; // Flag to indicate when the instructor data is fully loaded

                // Fetch instructor data with pagination
                this.fetchInstructorData();
            },

            /**
             * Fetch instructor data from the Moochub API with pagination.
             */
            fetchInstructorData: function () {
                const self = this;
                const moochubApiUrl = '/api/moochub/v1/moochubinfo/';
            
                async function fetchAllPages(url) {
                    console.log("fetch instuctor pages")
                    try {
                        const response = await $.getJSON(url);
            
                        // Process current page data
                        response.data.forEach(course => {
                            const courseCode = course.attributes.courseCode || course.attributes.id;
                            const instructors = course.attributes.instructor || [];
                            self.instructorMap[courseCode] = instructors.map(i => i.name).join(', ') || 'Instructor: Not Available';
                        });
            
                        // Fetch next page if available
                        if (response.links && response.links.next) {
                            console.log("there is another page")
                            await fetchAllPages(response.links.next); // Properly await next page
                        }
                    } catch (error) {
                        console.error('Failed to fetch instructor data:', error);
                    }
                }
            
                fetchAllPages(moochubApiUrl).then(() => {
                    self.instructorDataLoaded = true;
                    self.trigger('instructorMap:loaded');
                    console.log('Instructor map fully loaded:', self.instructorMap);
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

                    // Use instructor names from the instructorMap
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

                // Log for debugging
                console.log('Parsed course data with instructor names:', this.courseCards);
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
