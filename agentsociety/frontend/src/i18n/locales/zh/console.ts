export default {
    table: {
        id: "ID",
        name: "名称",
        numDay: "天数",
        status: "状态",
        currentDay: "当前天数",
        currentTime: "当前时间",
        config: "配置",
        error: "报错",
        inputTokens: "输入Token数",
        outputTokens: "输出Token数",
        createdAt: "创建时间",
        updatedAt: "更新时间",
        action: "操作"
    },
    statusEnum: {
        "0": "未开始",
        "1": "运行中",
        "2": "已完成",
        "3": "错误中断",
        "4": "已停止"
    },
    buttons: {
        goto: "查看",
        stop: "停止",
        detail: "详情",
        viewLog: "查看日志",
        export: "全部导出",
        exportArtifacts: "导出产物",
        exportExperimentPack: "导出可玩实验包",
        delete: "删除",
        createExperiment: "创建实验"
    },
    modals: {
        experimentDetail: "实验详情",
        experimentLog: "实验日志",
        refresh: "刷新",
        manualRefresh: "手动刷新",
        refreshing: "正在刷新...",
        refreshIntervals: {
            oneSecond: "每秒刷新",
            fiveSeconds: "每5秒刷新",
            tenSeconds: "每10秒刷新",
            thirtySeconds: "每30秒刷新"
        }
    },
    confirmations: {
        stopExperiment: "确定要停止这个实验吗？",
        deleteExperiment: "确定要删除这个实验吗？"
    },
    messages: {
        stopSuccess: "停止实验成功",
        stopFailed: "停止实验失败：",
        deleteSuccess: "删除实验成功",
        deleteFailed: "删除实验失败：",
        noToken: "未找到token，请登录"
    }
};
