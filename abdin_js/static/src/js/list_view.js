odoo.define("abdin_js.ListNumber", function (require) {
  "use strict";

  var core = require("web.core");
  var ListRenderer = require("web.ListRenderer");
  var pyUtils = require("web.py_utils");
  var _t = core._t;
  var py = window.py;

  ListRenderer.include({
    _getNumberOfCols: function () {
      var columns = this._super();
      columns += 1;
      return columns;
    },
    _renderFooter: function (isGrouped) {
      var $footer = this._super(isGrouped);
      $footer.find("tr").prepend($("<td>"));
      return $footer;
    },
    _renderGroupRow: function (group, groupLevel) {
      var $row = this._super(group, groupLevel);
      if (this.mode !== "edit" || this.hasSelectors) {
        $row.find("th.o_group_name").after($("<td>"));
      }
      return $row;
    },
    _renderGroups: function (data, groupLevel) {
      var self = this;
      var _self = this;
      groupLevel = groupLevel || 0;
      var result = [];
      var $tbody = $("<tbody>");
      _.each(data, function (group) {
        if (!$tbody) {
          $tbody = $("<tbody>");
        }
        $tbody.append(self._renderGroupRow(group, groupLevel));
        if (group.data.length) {
          result.push($tbody);
          // render an opened group
          if (group.groupedBy.length) {
            // the opened group contains subgroups
            result = result.concat(
              self._renderGroups(group.data, groupLevel + 1)
            );
          } else {
            // the opened group contains records
            var $records = _.map(group.data, function (record, index) {
              //Nilesh
              if (_self.mode !== "edit" || _self.hasSelectors) {
                return self
                  ._renderRow(record)
                  .prepend($("<th class='o_list_row_count'>").html(index + 1)); //.prepend($('<td>'));
              } else {
                return self._renderRow(record);
              }
            });
            result.push($("<tbody>").append($records));
          }
          $tbody = null;
        }
      });
      if ($tbody) {
        result.push($tbody);
      }
      return result;
    },

    _renderHeader: function (isGrouped) {
      var $header = this._super(isGrouped);
      if (this.hasSelectors) {
        $header
          .find("th.o_list_record_selector")
          .before(
            $('<th class="o_list_row_number_header o_list_row_count">').html(
              "#"
            )
          );
        var advance_search = $header.find("tr.advance_search_row");
        if (
          advance_search.length &&
          advance_search.find("td.o_list_row_number_header").length == 0
        ) {
          advance_search.prepend(
            $('<td class="o_list_row_number_header">').html("&nbsp;")
          );
        }
      } else {
        if (this.mode !== "edit") {
          $header
            .find("tr")
            .prepend(
              $("<th class='o_list_row_number_header o_list_row_count'>").html(
                "#"
              )
            );
        }
      }
      //$header.find("tr").prepend($('<th>').html('#'));
      return $header;
    },

    _renderHeaderCell: function () {
      const $th = this._super.apply(this, arguments);
      // if ($th[0].innerHTML.length && this._hasVisibleRecords(this.state)) {
      const resizeHandle = document.createElement("span");
      resizeHandle.classList = "o_resize";
      resizeHandle.onclick = this._onClickResize.bind(this);
      resizeHandle.onmousedown = this._onStartResize.bind(this);
      $th.append(resizeHandle);
      // }
      return $th;
    },

    _renderRow: function (record) {
      var $row = this._super(record);
      if (this.mode !== "edit" && this.state.groupedBy.length == 0) {
        var index = this.state.data.findIndex(function (e) {
          return record.id === e.id;
        });
        if (index !== -1) {
          $row.prepend($("<th class='o_list_row_count'>").html(index + 1));
        }
      }
      return $row;
    },
    _renderBodyCell: function (record, node, colIndex, options) {
      var $td = this._super.apply(this, arguments);
      var ctx = this.getEvalContext(record);
      this.addClass($td, node, ctx);
      this.formatNode($td, node, ctx);

      return $td;
    },
    addClass: function ($el, node, ctx) {
      if (!node.attrs.options) {
        return;
      }
      if (node.tag !== "field") {
        return;
      }
      var nodeOptions = node.attrs.options;
      if (!_.isObject(nodeOptions)) {
        nodeOptions = pyUtils.py_eval(nodeOptions);
        if (nodeOptions["add_class"]) {
          var conditions = nodeOptions["add_class"].replace(/`/g, "'");
          for (var cond of conditions.split(",")) {
            if (cond.includes(":")) {
              var [myClass, expression] = cond.split(":");
              expression = py.parse(py.tokenize(expression));
              if (py.evaluate(expression, ctx).toJSON()) {
                $el.addClass(myClass);
              }
            }
          }
        }
      }
    },
    formatNode: function ($el, node, ctx) {
      if (!node.attrs.options) {
        return;
      }
      if (node.tag !== "field") {
        return;
      }
      var nodeOptions = node.attrs.options;
      if (!_.isObject(nodeOptions)) {
        nodeOptions = pyUtils.py_eval(nodeOptions);
        if (nodeOptions["format"]) {
          var int_format = nodeOptions["format"];
          if (int_format === "integer") {
            if ($el.attr("title")) {
              var new_integer = $el.attr("title").replace(/,/g, "");
              // $el.attr('title',new_integer);
              $el.text(new_integer);
            }
          }
        }
      }
    },
    getEvalContext: function (record) {
      var ctx = _.extend({}, record.data, pyUtils.context());
      for (var key in ctx) {
        var value = ctx[key];
        if (ctx[key] instanceof moment) {
          // Date/datetime fields are represented w/ Moment objects
          // docs: https://momentjs.com/
          ctx[key] = value.format("YYYY-MM-DD hh:mm:ss");
        }
      }
      return ctx;
    },
  });
});
