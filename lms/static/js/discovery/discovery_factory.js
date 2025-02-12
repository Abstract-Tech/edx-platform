(function (define) {
    'use strict';

    define(['backbone', 'js/discovery/models/search_state', 'js/discovery/collections/filters',
        'js/discovery/views/search_form', 'js/discovery/views/courses_listing',
        'js/discovery/views/filter_bar', 'js/discovery/views/refine_sidebar'],
    function (Backbone, SearchState, Filters, SearchForm, CoursesListing, FilterBar, RefineSidebar) {
        return function (meanings, searchQuery, userLanguage, userTimezone) {
            var dispatcher = _.extend({}, Backbone.Events);
            var search = new SearchState();
            var filters = new Filters();
            var form = new SearchForm();
            var filterBar = new FilterBar({ collection: filters });
            var refineSidebar = new RefineSidebar({
                collection: search.discovery.facetOptions,
                meanings: meanings
            });
            var listing;
            var courseListingModel = search.discovery;
            courseListingModel.userPreferences = {
                userLanguage: userLanguage,
                userTimezone: userTimezone
            };

            // Instructor mapping logic with pagination
            var instructorMap = {}; // Store instructor names for each course
            var moochubApiUrl = '/api/moochub/v1/moochubinfo/';

            /**
             * Fetch all pages recursively and populate the instructorMap.
             */
            function fetchAllPages(url, onComplete) {
                $.getJSON(url)
                    .done(function (response) {
                        // Process the current page data
                        response.data.forEach(function (course) {
                            const courseCode = course.attributes.courseCode || course.attributes.id;
                            const instructors = course.attributes.instructor || [];
                            instructorMap[courseCode] = instructors.map(i => i.name).join(', ') || 'Instructor: Not Available';
                        });

                        // Check if there is a next page and recursively fetch
                        if (response.links && response.links.next && response.links.next.length > 0) {
                            console.log('Next page found:', response.links.next);
                            fetchAllPages(response.links.next, onComplete);
                        } else {
                            // No more pages, trigger the completion callback
                            console.log('Instructor map fully loaded:', instructorMap);
                            if (onComplete) onComplete();
                        }

                    })
                    .fail(function () {
                        console.error('Failed to fetch instructor data from Moochub API');
                    });
            }

            // Initialize the application after loading all instructor data
            fetchAllPages(moochubApiUrl, function () {
                // Initialize the CoursesListing after instructor data is loaded
                listing = new CoursesListing({ model: courseListingModel });

                dispatcher.listenTo(listing, 'next', function () {
                    search.loadNextPage();
                });

                dispatcher.listenTo(search, 'next', function () {
                    listing.renderNext();
                });

                dispatcher.listenTo(search, 'search', function (query, total) {
                    if (total > 0) {
                        form.showFoundMessage(total);
                        if (query) {
                            filters.add(
                                { type: 'search_query', query: query, name: quote(query) },
                                { merge: true }
                            );
                        }
                    } else {
                        form.showNotFoundMessage(query);
                        filters.reset();
                    }
                    form.hideLoadingIndicator();
                    listing.render();
                    refineSidebar.render();
                });

                // Modify the CoursesListing to include instructor names
                var originalRender = listing.render;
                listing.render = function () {
                    // Inject instructor names into the course data
                    courseListingModel.courseCards.each(function (course) {
                        var courseCode = course.get('number') || course.get('id');
                        course.set('instructor_names', instructorMap[courseCode] || 'Instructor: Not Available');
                    });

                    // Call the original render function
                    return originalRender.apply(listing, arguments);
                };

                form.doSearch(searchQuery); // Start the search after initializing everything
            });

            dispatcher.listenTo(form, 'search', function (query) {
                filters.reset();
                form.showLoadingIndicator();
                search.performSearch(query, filters.getTerms());
            });

            dispatcher.listenTo(refineSidebar, 'selectOption', function (type, query, name) {
                form.showLoadingIndicator();
                if (filters.get(type)) {
                    removeFilter(type);
                } else {
                    filters.add({ type: type, query: query, name: name });
                    search.refineSearch(filters.getTerms());
                }
            });

            dispatcher.listenTo(filterBar, 'clearFilter', removeFilter);

            dispatcher.listenTo(filterBar, 'clearAll', function () {
                form.doSearch('');
            });

            dispatcher.listenTo(search, 'error', function () {
                form.showErrorMessage(search.errorMessage);
                form.hideLoadingIndicator();
            });

            function removeFilter(type) {
                form.showLoadingIndicator();
                filters.remove(type);
                if (type === 'search_query') {
                    form.doSearch('');
                } else {
                    search.refineSearch(filters.getTerms());
                }
            }

            function quote(string) {
                return '"' + string + '"';
            }
        };
    });
}(define || RequireJS.define));
