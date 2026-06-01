export default {
    table: {
        id: "ID",
        name: "Name",
        numDay: "Num Day",
        status: "Status",
        currentDay: "Current Day",
        currentTime: "Current Time",
        config: "Config",
        error: "Error",
        inputTokens: "Input Tokens",
        outputTokens: "Output Tokens",
        createdAt: "Created At",
        updatedAt: "Updated At",
        action: "Action"
    },
    statusEnum: {
        "0": "Not Started",
        "1": "Running",
        "2": "Completed",
        "3": "Error Interrupted",
        "4": "Stopped"
    },
    buttons: {
        goto: "Goto",
        stop: "Stop",
        detail: "Detail",
        viewLog: "View Log",
        export: "Export All",
        exportArtifacts: "Export Artifacts",
        exportExperimentPack: "Export Experiment Pack",
        delete: "Delete",
        createExperiment: "Create Experiment"
    },
    modals: {
        experimentDetail: "Experiment Detail",
        experimentLog: "Experiment Log",
        refresh: "Refresh",
        manualRefresh: "Manual refresh",
        refreshing: "Refreshing...",
        refreshIntervals: {
            oneSecond: "Every 1 second",
            fiveSeconds: "Every 5 seconds",
            tenSeconds: "Every 10 seconds",
            thirtySeconds: "Every 30 seconds"
        }
    },
    confirmations: {
        stopExperiment: "Are you sure to stop this experiment?",
        deleteExperiment: "Are you sure to delete this experiment?"
    },
    messages: {
        stopSuccess: "Stop experiment successfully",
        stopFailed: "Failed to stop experiment:",
        deleteSuccess: "Delete experiment successfully",
        deleteFailed: "Failed to delete experiment:",
        noToken: "No token found, please login"
    }
};
