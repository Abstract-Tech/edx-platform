(function(define) {
    define([
        'jquery',
        'underscore',
        'backbone',
        'gettext',
        'js/discovery/views/course_card',
        'edx-ui-toolkit/js/utils/html-utils'
    ], function($, _, Backbone, gettext, CourseCardView, HtmlUtils) {
        'use strict';

        return Backbone.View.extend({

            el: 'div.courses',
            $window: $(window),
            $document: $(document),

            initialize: function() {
                this.$currentCoursesList = this.$el.find('.current-courses-listing');
                this.$upcomingCoursesList = this.$el.find('.upcoming-courses-listing');
                this.$selfPacedCoursesList = this.$el.find('.self-paced-courses-listing');
                this.$pastCoursesList = this.$el.find('.past-courses-listing');
                this.attachScrollHandler();
            },

            render: function() {
                this.$currentCoursesList.empty();
                this.$upcomingCoursesList.empty();
                this.$selfPacedCoursesList.empty();
                this.$pastCoursesList.empty();
                this.renderItems();
                return this;
            },

            renderNext: function() {
                this.renderItems();
                this.isLoading = false;
            },

            sortCoursesByStartDateDesc: function(course1, course2) {
                var date1 = new Date(course1.attributes.start);
                var date2 = new Date(course2.attributes.start);
                return date2.getTime() - date1.getTime()
            },

            renderItems: function() {
                /* eslint no-param-reassign: [2, { "props": true }] */
                var latest = this.model.latest();
                var currentDate = new Date();
                var past6Weeks = new Date(new Date() - 1000*60*60*24*42)
                var currentCourses = [];
                var upcomingCourses = [];
                var selfPacedCourses = [];
                var pastCourses = [];
                var currentCoursesSelfPaced = [];
                var upcomingCoursesSelfPaced = [];


                for (var i = 0; i < latest.length; i++) {
                    var course = latest[i];
                    var course_start = new Date(course.attributes.start);

                    if (course.attributes.self_paced  && (course_start <= past6Weeks)) {
                        selfPacedCourses.push(course);
                    } else {
                        var course_end;
                        if (course.attributes.end === undefined) {
                            course_end = undefined;
                        } else {
                            course_end = new Date(course.attributes.end);
                        }
                        if ((course_start <= currentDate) && ((course_end >= currentDate) || (course_end === undefined))) {
                            if(course.attributes.self_paced) {
                                currentCoursesSelfPaced.push(course);
                            }else{
                            currentCourses.push(course);
                            }
                        } else if ((course_start > currentDate) && ((course_end >= currentDate) || (course_end === undefined))) {
                        
                            if(course.attributes.self_paced) {
                                upcomingCoursesSelfPaced.push(course);
                            }else{
                                upcomingCourses.push(course);
                            }
                        
                        }
                         else if ((course_start < currentDate) && ((course_end <= currentDate) || (course_end === undefined))) {
                            pastCourses.push(course);
                        }
                    }
                }

                console.log("before sorting");
                console.log(`currentCourses: ${currentCourses} \n upcomingCourses: ${upcomingCourses} \n selfPacedCourses: ${selfPacedCourses} \n pastCourses: ${pastCourses}`);

                currentCourses.sort(this.sortCoursesByStartDateDesc);
                upcomingCourses.sort(this.sortCoursesByStartDateDesc);
                selfPacedCourses.sort(this.sortCoursesByStartDateDesc);
                pastCourses.sort(this.sortCoursesByStartDateDesc);
                currentCoursesSelfPaced.sort(this.sortCoursesByStartDateDesc);
                currentCourses = [ ...currentCourses, ...currentCoursesSelfPaced];

                var currentCoursesItems = currentCourses.map(function(result) {
                    result.userPreferences = this.model.userPreferences;
                    result.attributes.instructor_names = result.attributes.instructor_names || 'Instructor: Not Available444';
                    var item = new CourseCardView({ model: result });
                    return item.render().el;
                }, this);
                
                

                upcomingCourses = [ ...upcomingCourses, ...upcomingCoursesSelfPaced];   

                console.log("after sorting");
                console.log(`currentCourses: ${currentCourses} \n upcomingCourses: ${upcomingCourses} \n selfPacedCourses: ${selfPacedCourses} \n pastCourses: ${pastCourses}`);



                var upcomingCoursesItems = upcomingCourses.map(function(result) {
                    result.userPreferences = this.model.userPreferences;
                    result.set('instructor_names', result.attributes.instructor_names || 'Instructor: Not Available555');
                    var item = new CourseCardView({model: result});
                    return item.render().el;
                }, this);
                

                var selfPacedCoursesItems = selfPacedCourses.map(function(result) {
                    result.userPreferences = this.model.userPreferences;
                    result.set('instructor_names', result.attributes.instructor_names || 'Instructor: Not Available6666');
                    var item = new CourseCardView({model: result});
                    return item.render().el;
                }, this);

                var pastCoursesItems = pastCourses.map(function(result) {
                    result.userPreferences = this.model.userPreferences;
                    result.set('instructor_names', result.attributes.instructor_names || 'Instructor: Not Available6777');
                    var item = new CourseCardView({model: result});
                    return item.render().el;
                }, this);

                if (currentCourses.length) {
                    HtmlUtils.append(
                        this.$currentCoursesList,
                        HtmlUtils.HTML(currentCoursesItems)
                    );
                    if ($(".current-courses-header").length === 0) {
                        this.$currentCoursesList.before("<h2 class='current-courses-header'>Current courses</h2>");
                    }
                } else {
                    if ($(".current-courses-header").length === 1) {
                        $(".current-courses-header").remove();
                    }
                }

                if (upcomingCourses.length) {
                    HtmlUtils.append(
                        this.$upcomingCoursesList,
                        HtmlUtils.HTML(upcomingCoursesItems)
                    );
                    if ($(".upcoming-courses-header").length === 0) {
                        this.$upcomingCoursesList.before("<h2 class='upcoming-courses-header'>Upcoming courses</h2>");
                    }
                } else {
                    if ($(".upcoming-courses-header").length === 1) {
                        $(".upcoming-courses-header").remove();
                    }
                }

                if (selfPacedCourses.length) {
                    HtmlUtils.append(
                        this.$selfPacedCoursesList,
                        HtmlUtils.HTML(selfPacedCoursesItems)
                    );
                    if ($(".self-paced-courses-header").length === 0) {
                        this.$selfPacedCoursesList.before("<h2 class='self-paced-courses-header'>Self paced courses</h2>");
                    }
                } else {
                    if ($(".self-paced-courses-header").length === 1) {
                        $(".self-paced-courses-header").remove();
                    }
                }

                if (pastCourses.length) {
                    HtmlUtils.append(
                        this.$pastCoursesList,
                        HtmlUtils.HTML(pastCoursesItems)
                    );
                    if ($(".past-courses-header").length === 0) {
                        this.$pastCoursesList.before("<h2 class='past-courses-header'>Past courses</h2>");
                    }
                } else {
                    if ($(".past-courses-header").length === 1) {
                        $(".past-courses-header").remove();
                    }
                }

                /* eslint no-param-reassign: [2, { "props": false }] */
            },

            attachScrollHandler: function() {
                this.$window.on('scroll', _.throttle(this.scrollHandler.bind(this), 400));
            },

            scrollHandler: function() {
                if (this.isNearBottom() && !this.isLoading) {
                    this.trigger('next');
                    this.isLoading = true;
                }
            },

            isNearBottom: function() {
                var scrollBottom = this.$window.scrollTop() + this.$window.height();
                var threshold = this.$document.height() - 200;
                return scrollBottom >= threshold;
            }

        });
    });
}(define || RequireJS.define));