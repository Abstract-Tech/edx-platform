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

                if ($('.courses-container').attr('data-theme') === 'theme-one') {
                    console.log("Rendering courses with quarter-based logic for Theme 1...");
                    this.renderQuarterBasedItems();
                } else {
                    console.log("Rendering courses with standard categorization for Theme 2...");
                    this.renderOriginalItems();
                }
                
            },

            renderNext: function() {
                if (this.$el.hasClass('theme-one')) {
                    this.renderQuarterBasedItems();
                } else {
                    this.renderOriginalItems();
                }
                this.isLoading = false;
            },

            sortByEndDate: function(course1, course2) {
                var d1 = new Date(course1.attributes.end);
                var d2 = new Date(course2.attributes.end);
                return d1 - d2;
            },
            

            renderQuarterBasedItems: function() {
                var latest = this.model.latest();
                var currentDate = new Date();
                console.log("Total courses received:", latest.length);
            
                function getQuarterInfo(dateObj) {
                    var month = dateObj.getMonth();
                    var year = dateObj.getFullYear();
                    var quarterIndex, label, startMonth, endMonth;
            
                    if (month >= 0 && month <= 2) {
                        quarterIndex = 1;
                        label = "January - March " + year;
                        startMonth = 0; endMonth = 2;
                    } else if (month >= 3 && month <= 5) {
                        quarterIndex = 2;
                        label = "April - June " + year;
                        startMonth = 3; endMonth = 5;
                    } else if (month >= 6 && month <= 8) {
                        quarterIndex = 3;
                        label = "July - September " + year;
                        startMonth = 6; endMonth = 8;
                    } else {
                        quarterIndex = 4;
                        label = "October - December " + year;
                        startMonth = 9; endMonth = 11;
                    }
            
                    return {
                        quarterIndex: quarterIndex,
                        year: year,
                        startMonth: startMonth,
                        endMonth: endMonth,
                        label: label
                    };
                }
            
                function quarterIndexToQuarterInfo(qIdx, year) {
                    var label = "", startMonth = 0, endMonth = 0;
                    if (qIdx === 1) {
                        label = "January - March " + year;
                        startMonth = 0; endMonth = 2;
                    } else if (qIdx === 2) {
                        label = "April - June " + year;
                        startMonth = 3; endMonth = 5;
                    } else if (qIdx === 3) {
                        label = "July - September " + year;
                        startMonth = 6; endMonth = 8;
                    } else {
                        label = "October - December " + year;
                        startMonth = 9; endMonth = 11;
                    }
                    return {
                        quarterIndex: qIdx,
                        year: year,
                        startMonth: startMonth,
                        endMonth: endMonth,
                        label: label
                    };
                }
            
                function getNextNQuarters(baseQuarter, n) {
                    var arr = [];
                    var qIndex = baseQuarter.quarterIndex;
                    var yr = baseQuarter.year;
            
                    for (var i = 0; i < n; i++) {
                        var qObj = quarterIndexToQuarterInfo(qIndex, yr);
                        arr.push(qObj);
                        qIndex++;
                        if (qIndex > 4) {
                            qIndex = 1;
                            yr++;
                        }
                    }
                    return arr;
                }
            
                var nowQuarter = getQuarterInfo(currentDate);
                var quartersToShow = getNextNQuarters(nowQuarter, 4);
                console.log("Quarters to show:", quartersToShow.map(q => q.label));
            
                var quarterToCourses = {};
                _.each(quartersToShow, function(q) {
                    quarterToCourses[q.label] = [];
                });
            
                for (var i = 0; i < latest.length; i++) {
                    var course = latest[i];
            
                    // ✅ SKIP if missing essential data
                    var content = course.attributes && course.attributes.content;
                    var displayName = content && content.display_name;

                    if (!displayName || course.attributes.self_paced) {
                        console.warn("Skipping course due to missing/invalid data:", course.attributes);
                        continue;
                    }
                    

            
                    var startDate = new Date(course.attributes.start);
                    console.log(`✅ Course: "${displayName}" starts on ${startDate.toISOString()}`);

                    for (var j = 0; j < quartersToShow.length; j++) {
                        var qInfo = quartersToShow[j];
                        var startBoundary = new Date(qInfo.year, qInfo.startMonth, 1, 0, 0, 0);
                        var lastDay = new Date(qInfo.year, qInfo.endMonth + 1, 0).getDate();
                        var endBoundary = new Date(qInfo.year, qInfo.endMonth, lastDay, 23, 59, 59);
            
                        if (startDate >= startBoundary && startDate <= endBoundary) {
                            quarterToCourses[qInfo.label].push(course);
                            console.log(`→ Assigned to quarter: ${qInfo.label}`);
                            break;
                        }
                    }
                }
            
                var finalHtml = "";
                _.each(quartersToShow, function(qObj, idx) {
                    var headingTitle = (idx === 0) ? "Current modules and micro-degrees" : "Upcoming modules and micro-degrees";
                    var quarterLabel = qObj.label;
            
                    var itemsHtml = "";

                    console.log(`Rendering quarter section: ${quarterLabel} with ${quarterToCourses[quarterLabel].length} courses`);
                    _.each(quarterToCourses[qObj.label], function(courseModel) {
                        var cardView = new CourseCardView({ model: courseModel });
                        var renderedEl = cardView.render().el;
            
                        // ✅ CHECK IF CARD IS VISUALLY VALID
                        var cardHtml = renderedEl && renderedEl.outerHTML ? renderedEl.outerHTML.trim() : "";

                        if (cardHtml && cardHtml.length > 50 && !cardHtml.includes('<li class="courses-listing-item"></li>')) {
                            itemsHtml += '<li class="courses-listing-item">' + cardHtml + '</li>';
                        } else {
                            console.warn("❌ Skipped rendering due to invalid/malformed card content:", courseModel.attributes.title || 'Unnamed');
                        }
                                                
                    });
            
                    if (itemsHtml !== "") {
                        var quarterLabelDescription = "The courses are modules of our M.Sc. and MBA programs. However, anyone can book these courses as stand-alone Micro Degree programs for a fee of €900.";
            
                        finalHtml += '<div class="quarter-section">';
                        finalHtml += '<h2 class="quarter-label">' + headingTitle + ': ' + quarterLabel + '</h2>';
                        finalHtml += '<p class="quarter-label-description">' + quarterLabelDescription + '</p>';
                        finalHtml += '<ul class="courses-listing courses-list">' + itemsHtml + '</ul>';
                        finalHtml += '</div>';
                    } else {
                        console.log("❌ No valid items to render for quarter:", quarterLabel);
                    }
                });
            
                var $container = this.$el.find('.courses-listing.courses-list');
                if (!$container.length) {
                    $container = this.$el;
                }
                $container.empty();
                $container.append(finalHtml);

                // 🔥 Remove empty course listing <li> tags manually
                $container.find('li.courses-listing-item').each(function () {
                    const $el = $(this);
                    const article = $el.find('article.course');
                    const name = $el.find('.course-name span').text().trim() || article.attr('aria-label');
                    const image = $el.find('img').attr('src');

                    const isValid = name && image;
                    if (!isValid) {
                        console.warn(" Removing broken or empty course card:", name || "No name");
                        $el.remove();
                    }
                });

                
                
                


            },
            
        

            renderOriginalItems: function() {
                var latest = this.model.latest();
                var currentDate = new Date();
                var currentCourses = [];
                var upcomingCourses = [];
                var selfPacedCourses = [];
                var pastCourses = [];
            
                for (var i = 0; i < latest.length; i++) {
                    var course = latest[i];
                    if (course.attributes.self_paced) {
                        selfPacedCourses.push(course);
                    } else {
                        var course_start = new Date(course.attributes.start);
                        var course_end = course.attributes.end ? new Date(course.attributes.end) : undefined;
            
                        if ((course_start <= currentDate) && ((course_end >= currentDate) || (course_end === undefined))) {
                            currentCourses.push(course);
                        } else if (course_start > currentDate) {
                            upcomingCourses.push(course);
                        } else {
                            pastCourses.push(course);
                        }
                    }
                }
            
                var currentCoursesItems = currentCourses.map(function(result) {
                    var item = new CourseCardView({model: result});
                    return item.render().el;
                });
            
                var upcomingCoursesItems = upcomingCourses.map(function(result) {
                    var item = new CourseCardView({model: result});
                    return item.render().el;
                });
            
                var selfPacedCoursesItems = selfPacedCourses.map(function(result) {
                    var item = new CourseCardView({model: result});
                    return item.render().el;
                });
            
                var pastCoursesItems = pastCourses.map(function(result) {
                    var item = new CourseCardView({model: result});
                    return item.render().el;
                });
            
                if (currentCourses.length) {
                    HtmlUtils.append(this.$currentCoursesList, HtmlUtils.HTML(currentCoursesItems));
                    if ($(".current-courses-header").length === 0) {
                        this.$currentCoursesList.before("<h2 class='current-courses-header'>Current courses</h2>");
                    }
                } else {
                    $(".current-courses-header").remove();
                }

                if (upcomingCourses.length) {
                    HtmlUtils.append(this.$upcomingCoursesList, HtmlUtils.HTML(upcomingCoursesItems));
                    if ($(".upcoming-courses-header").length === 0) {
                        this.$upcomingCoursesList.before("<h2 class='upcoming-courses-header'>Upcoming courses</h2>");
                    }
                } else {
                    $(".upcoming-courses-header").remove();
                }

                if (selfPacedCourses.length) {
                    HtmlUtils.append(this.$selfPacedCoursesList, HtmlUtils.HTML(selfPacedCoursesItems));
                    if ($(".self-paced-courses-header").length === 0) {
                        this.$selfPacedCoursesList.before("<h2 class='self-paced-courses-header'>Self paced courses</h2>");
                    }
                } else {
                    $(".self-paced-courses-header").remove();
                }

                if (pastCourses.length) {
                    HtmlUtils.append(this.$pastCoursesList, HtmlUtils.HTML(pastCoursesItems));
                    if ($(".past-courses-header").length === 0) {
                        this.$pastCoursesList.before("<h2 class='past-courses-header'>Past courses</h2>");
                    }
                } else {
                    $(".past-courses-header").remove();
                }
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
