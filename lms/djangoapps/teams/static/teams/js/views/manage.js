(function(define) {
    'use strict';

    define([
        'backbone',
        'underscore',
        'gettext',
        'edx-ui-toolkit/js/utils/html-utils',
        'common/js/components/utils/view_utils',
        'teams/js/views/team_utils',
        'text!teams/templates/manage.underscore'
    ], function(Backbone, _, gettext, HtmlUtils, ViewUtils, TeamUtils, manageTemplate) {
        var revealBanner = function() {
            var $banner = $('#team-management-assign .page-banner');
            if ($banner.length) {
                $banner.prop('hidden', false)
                    .removeAttr('hidden')
                    .attr('aria-hidden', false);
            }
        };

        var ManageView = Backbone.View.extend({

            srInfo: {
                id: 'heading-manage',
                text: gettext('Manage')
            },

            events: {
                'click #download-team-csv': 'downloadCsv',
                'change #upload-team-csv-input': 'setTeamMembershipCsv',
                'click #upload-team-csv': ViewUtils.withDisabledElement('uploadCsv')
            },

            initialize: function(options) {
                this.teamEvents = options.teamEvents;
                this.csvUploadUrl = options.teamMembershipManagementUrl;
                this.csvDownloadUrl = options.teamMembershipManagementUrl;
            },

            render: function() {
                HtmlUtils.setHtml(
                    this.$el,
                    HtmlUtils.template(manageTemplate)({})
                );
                this.$('#team-management-assign .page-banner')
                    .removeAttr('hidden')
                    .prop('hidden', false)
                    .attr('aria-hidden', true)
                    .hide();
                this.delegateEvents(this.events);
                return this;
            },

            downloadCsv: function() {
                window.location.href = this.csvDownloadUrl;
            },

            setTeamMembershipCsv: function(event) {
                this.membershipFile = event.target.files[0];

                // enable the upload button when a file is selected
                if (this.membershipFile) {
                    $('#upload-team-csv').removeClass('is-disabled').attr('aria-disabled', false);
                } else {
                    $('#upload-team-csv').addClass('is-disabled').attr('aria-disabled', true);
                }
            },

            uploadCsv: function() {
                var formData = new FormData();
                formData.append('csv', this.membershipFile); // xss-lint: disable=javascript-jquery-append
                revealBanner();

                return $.ajax({
                    type: 'POST',
                    url: this.csvUploadUrl,
                    data: formData,
                    processData: false, // tell jQuery not to process the data
                    contentType: false // tell jQuery not to set contentType
                }).done(
                    this.handleCsvUploadSuccess
                ).fail(
                    this.handleCsvUploadFailure
                );
            },

            handleCsvUploadSuccess: function(data) {
                TeamUtils.showInfoBanner(data.message, false);

                // Implement a teams:update event (TODO MST-44)
            },

            handleCsvUploadFailure: function(jqXHR) {
                TeamUtils.showInfoBanner(jqXHR.responseJSON.errors, true);
            }
        });
        return ManageView;
    });
}).call(this, define || RequireJS.define);
