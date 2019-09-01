(function () {
    "use strict";
    var masterChart = document.getElementById("chart"),
        // controls that specify the traces in the chart
        traces = [],
        plotControlIds = Array.from(document.getElementsByClassName("plot-controls")[0].getElementsByTagName("select")).map(x => x.id.replace('-', ' '));
    const DEF_AXIS_RANGE = [0, 1];
    // create empty chart
    Plotly.newPlot(masterChart, [], {
        autosize: true,
        width: document.documentElement.clientWidth,
        hovermode: "closest",
        xaxis: {
            range: DEF_AXIS_RANGE
        },
        yaxis: {
            range: DEF_AXIS_RANGE
        }
    }, {
        responsive: true,
        displaylogo: false
    });

    // show page after chart is created
    masterChart.parentElement.classList.remove("d-none");

    function createOptionsDoc(opts) {
        var optionsDoc = document.createDocumentFragment();
        for (let i = 0; i < opts.length; i++) {
            let opt = document.createElement("option"),
                v = opts[i];
            opt.setAttribute("value", v);
            opt.textContent = v;
            optionsDoc.appendChild(opt);
        }
        return optionsDoc;
    }

    // takes two trace objects and sees if they're equal
    function compareTraces(a, b) {
        // return false if either one of the arguments is not an object
        if (typeof (a) !== "object" || typeof (b) !== "object")
            return false;
        // see if both objects have the same address then surely they're the same
        if (a === b)
            return true;

        var aKeys = Object.keys(a),
            bKeys = Object.keys(b);
        if (aKeys.length !== bKeys.length)
            return false;

        for (let i = 0; i < aKeys.length; i++) {
            let key = aKeys[i];
            if (!(bKeys.includes(key)))
                return false;
            if (a[key] !== b[key])
                return false;
        }
        return true;
    }

    function sendRequest(uri, dataHandler, options = {}, cleanUp) {
        var ok;
        fetch(uri, options).then(res => {
            ok = res.ok;
            return res.json();
        }).then(data => {
            if (!ok)
                return Promise.reject(data.message);
            if (dataHandler)
                dataHandler(data);
        }).catch(err => {
            console.error(`Error occurred fetching ${uri}:`, err);
            // if a clean up function is defined then call it
            if (cleanUp)
                cleanUp();
        });
    }

    function clearChart() {
        var numTraces = masterChart.data.length;
        if (numTraces === 0)
            return false;

        var traceIdxs = new Array(numTraces);
        for (let i = 0; i < numTraces; i++)
            traceIdxs[i] = i;
        // delete all traces from graph
        Plotly.deleteTraces(masterChart, traceIdxs);
        return true;
    }

    var controlSwitch = function (controls = [], btnIds = []) {
        var btns = (["plot", "reset", "load", "save"].filter(id => btnIds.includes(id))).map(id => document.getElementById(id)),
            prevBtnStates = new Array(btns.length);

        function off() {
            for (let i = 0; i < controls.length; i++)
                controls[i].disabled = true;

            for (let i = 0; i < btns.length; i++) {
                let btn = btns[i];
                prevBtnStates[i] = btn.disabled;
                btn.disabled = true;
            }
        }

        function on() {
            for (let i = 0; i < controls.length; i++)
                controls[i].disabled = false;

            for (let i = 0; i < btns.length; i++) {
                let btn = btns[i];
                if (btn.id === "reset") {
                    // re-enable reset button if chart is not empty
                    if (masterChart.data.length > 0)
                        btn.disabled = false;
                } else
                    btn.disabled = prevBtnStates[i];
            }
        }

        return {
            off: off,
            on: on
        };
    }

    var invalidFilename = (function () {
        // BEWARE!!! The /g option in javascript regex has strange state-saving behavior
        const unixRegex = /[<>:"\/\\|?*\x00-\x1F]/,
            windowsRegex = /^(con|prn|aux|nul|com[0-9]|lpt[0-9])$/i,
            dotRegex = /^\.\.?$/;

        return function (name) {
            if (!name || name.length > 255)
                return true;

            if (unixRegex.test(name) || windowsRegex.test(name))
                return true;

            // file name cannot be a '.' or '..'
            if (dotRegex.test(name))
                return true;

            return false;
        };
    })();

    // check if a saved file already exists with that name
    function checkIfExists(filename) {
        var savedFiles = document.getElementById("saved-files").children;
        for (let i = 0; i < savedFiles.length; i++) {
            if (filename === savedFiles[i].value)
                return true;
        }
        return false;
    }

    // initialize plot
    sendRequest("/initplot", function (data) {
        // load plot controls
        var plotControls = document.getElementsByClassName("plot-controls")[0].getElementsByTagName("select"),
            controlsOptions = data.controls;

        for (let i = 0; i < plotControls.length; i++) {
            let c = plotControls[i];
            let opts = controlsOptions[plotControlIds[i]];
            c.appendChild(createOptionsDoc(opts));
            c.disabled = false;
        }

        // load axes options
        var axesControls = document.getElementsByClassName("axes-controls")[0].getElementsByTagName("select");
        for (let i = 0; i < axesControls.length; i++) {
            let c = axesControls[i];
            let opts = data[c.id];
            c.appendChild(createOptionsDoc(opts.opts));
            // load default option
            c.value = opts.def;
            c.disabled = false;
        }

        // load in saved files
        if (data.files.length > 0) {
            var savedFilesMenu = document.getElementById("saved-files");
            savedFilesMenu.appendChild(createOptionsDoc(data.files));
            savedFilesMenu.nextElementSibling.disabled = false;
        }

        Plotly.relayout(masterChart, {
            "xaxis.title.text": axesControls[0].value,
            "yaxis.title.text": axesControls[1].value
        });

        document.getElementById("plot").disabled = false;
    });

    document.getElementById("plot").addEventListener("click", function (e) {
        // disable reset, load, and save buttons; and changing axes while plotting because I'm nervous about any asynchronous funny business
        var axesControls = Array.from(document.getElementsByClassName("axes-controls")[0].getElementsByTagName("select")),
            toggleControls = controlSwitch(axesControls, ["plot", "reset", "load", "save"]);
        toggleControls.off();

        var plotControls = document.getElementsByClassName("plot-controls")[0].getElementsByTagName("select"),
            plotOpts = {};
        for (let i = 0; i < plotControls.length; i++)
            plotOpts[plotControlIds[i]] = plotControls[i].value;

        // check if trace is already plotted
        if (traces.some(t => compareTraces(t, plotOpts))) {
            toggleControls.on();
            return;
        }

        var axesOpts = [0, 0];
        for (let i = 0; i < axesControls.length; i++)
            axesOpts[i] = axesControls[i].value;

        sendRequest("/plot", function (data) {
            Plotly.addTraces(masterChart, data.trace);
            // this is the first trace in the chart
            if (masterChart.data.length === 1)
                Plotly.relayout(masterChart, {
                    "xaxis.autorange": true,
                    "xaxis.rangemode": "tozero",
                    "yaxis.autorange": true,
                    "yaxis.rangemode": "tozero"
                });

            traces.push(plotOpts);
            // re-enable controls
            toggleControls.on();
        }, {
            method: "POST",
            body: JSON.stringify({
                plot: plotOpts,
                axes: axesOpts
            }),
            headers: {
                "Content-Type": "application/json"
            }
        }, toggleControls.on);
    }, false);

    document.getElementById("reset").addEventListener("click", function (e) {
        // disable reset button because there will be no traces in chart
        this.disabled = true;
        clearChart();
        traces = [];
        // reset the axis range
        Plotly.relayout(masterChart, {
            "xaxis.range": DEF_AXIS_RANGE,
            "yaxis.range": DEF_AXIS_RANGE
        });
    }, false);

    document.getElementById("clear").addEventListener("click", function (e) {
        Array.from(document.getElementsByClassName("plot-controls")[0].getElementsByTagName("select")).forEach(elem => {
            elem.value = "";
        });
    }, false);

    for (let elem of document.getElementsByClassName("axes-controls")[0].getElementsByTagName("select"))
        elem.addEventListener("change", function (e) {
            // update the axis label
            Plotly.relayout(masterChart, {
                [this.id + ".title.text"]: this.value
            });

            // chart is empty then do not need to modify any traces
            if (masterChart.data.length === 0)
                return;

            // disable controls
            var axisControl = this,
                toggleControls = controlSwitch([axisControl], ["reset", "load", "save"]);
            toggleControls.off();

            sendRequest("/changeaxes", function (data) {
                for (let i = 0; i < data.length; i++)
                    Plotly.restyle(masterChart, data[i], [i]);
                toggleControls.on();
            }, {
                method: "POST",
                body: JSON.stringify({
                    axes: {
                        [axisControl.id]: axisControl.value
                    },
                    traces: traces
                }),
                headers: {
                    "Content-Type": "application/json"
                }
            }, toggleControls.on);
        }, false);

    document.getElementById("load").addEventListener("click", function (e) {
        var axesControls = Array.from(document.getElementsByClassName("axes-controls")[0].getElementsByTagName("select")),
            toggleControls = controlSwitch(axesControls, ["plot", "reset", "load", "save"]);
        toggleControls.off();
        var wasChartEmpty = !(clearChart());

        var filename = this.previousElementSibling.value;
        sendRequest("/load/" + filename, function (data) {
            Plotly.addTraces(masterChart, data.traces);
            // load axes into axes menus and set the axes in the chart
            var layout_update = {};
            axesControls.forEach((c, i) => {
                c.value = data.axes[i];
                layout_update[c.id + ".title.text"] = c.value;
                // if chart was not empty before and no traces are to be loaded then reset axes ranges to their default
                if (!wasChartEmpty && data.traces.length === 0)
                    layout_update[c.id + ".range"] = DEF_AXIS_RANGE;
                // else if the chart was empty before loading and the there are traces to be loaded
                // then change the axes ranges to their appropriate values
                else if (wasChartEmpty && data.traces.length > 0) {
                    layout_update[c.id + ".autorange"] = true;
                    layout_update[c.id + ".rangemode"] = "tozero";
                }
            });
            Plotly.relayout(masterChart, layout_update);

            toggleControls.on();
        }, {}, toggleControls.on);
    }, false);

    {
        let saveBtn = document.getElementById("save");
        saveBtn.previousElementSibling.addEventListener("input", function (e) {
            saveBtn.disabled = invalidFilename(this.value);
        }, false);

        saveBtn.addEventListener("click", function (e) {
            var toggleControls = controlSwitch([], ["save"]);
            toggleControls.off();

            var axesControls = document.getElementsByClassName("axes-controls")[0].getElementsByTagName("select"),
                axes = [0, 0];
            for (let i = 0; i < axesControls.length; i++)
                axes[i] = axesControls[i].value;

            var filename = this.previousElementSibling.value,
                alreadyExists = checkIfExists(filename);
            sendRequest("/save/" + filename, function (data) {
                // if file does not exist then add that file to the saved files menu 
                // and enable load button if this is the first file in the saved files menu
                if (!alreadyExists) {
                    let savedFilesMenu = document.getElementById("saved-files");
                    savedFilesMenu.appendChild(createOptionsDoc([filename]));
                    if (savedFilesMenu.childElementCount === 1)
                        document.getElementById("load").disabled = false;
                }

                toggleControls.on();
                alert("Chart was successfully saved!");
            }, {
                method: "POST",
                body: JSON.stringify({
                    traces: traces,
                    axes: axes
                }),
                headers: {
                    "Content-Type": "application/json"
                }
            }, toggleControls.on);
        }, false);
    }
})();
