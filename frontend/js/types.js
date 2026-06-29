/**
 * @fileoverview 伏羲前端 API 类型契约
 * 此文件定义所有后端 API 返回的数据结构，供 IDE 智能提示和代码审查使用
 * 
 * 后端基地址: http://172.25.30.200:8080
 * 
 * @module api-types
 */

/**
 * @name LoginResponse
 * POST /api/auth/login
 * @typedef {Object} LoginResponse
 * @property {string} token - JWT Token (格式: header.payload.signature)
 * @property {string} username - 用户名
 * @property {string} role - 角色 (admin/user)
 * @property {string} display_name - 显示名称，可能含中文
 */

/**
 * @name GraphResponse  
 * GET /api/graph
 * @typedef {Object} GraphResponse
 * @property {Object<string,GraphNode>} nodes - 节点映射 {节点名: 节点对象}
 * @property {GraphEdge[]} edges - 边数组
 * 
 * @typedef {Object} GraphNode
 * @property {string} type - 类型 (oa_module 等)
 * @property {number} mentions - 引用次数
 * @property {string[]} files - 关联文件列表
 * @property {Array<{from:string, to:string, relation:string}>} related
 * 
 * @typedef {Object} GraphEdge
 * @property {string} from - 源节点名
 * @property {string} to - 目标节点名  
 * @property {string} relation - 关系类型 (co_occurs 等)
 */

/**
 * @name WikiPagesResponse
 * GET /api/wiki/pages
 * @typedef {Object} WikiPagesResponse
 * @property {Array<{id:number, title:string}>} pages
 */

/**
 * @name OverviewResponse
 * GET /api/admin/metrics-summary
 * @typedef {Object} OverviewResponse
 * @property {boolean} ok
 * @property {number} chunks - 文档块总数
 * @property {number} latency_p50_ms - P50 延迟
 * @property {number} latency_p95_ms - P95 延迟
 * @property {number} latency_p99_ms - P99 延迟
 * @property {number} error_rate - 错误率 (0-1)
 * @property {number} uptime_hours - 运行小时数
 */

/**
 * @name OrganStatusResponse
 * GET /api/v2/status
 * @typedef {Object} OrganStatusResponse
 * @property {boolean} ok
 * @property {BaguaItem[]} bagua - 八卦器官数组 (8项)
 * 
 * @typedef {Object} BaguaItem
 * @property {string} trigram - 卦名 qian/kun/li/kan/zhen/dui/xun/gen
 * @property {string} symbol - 卦符号 ☰☷☲☵☳☱☴☶
 * @property {string} organ_id - 器官ID
 * @property {string} organ_name - 器官中文名
 * @property {boolean} alive - 是否在线
 * @property {string} status - healthy/busy/dead
 * @property {number} last_heartbeat_ago - 距上次心跳秒数
 * @property {Object} stats - 统计信息
 */

/**
 * @name EvalOverviewResponse
 * GET /api/evaluation/overview
 * @typedef {Object} EvalOverviewResponse
 * @property {Object} search_stats
 * @property {number} search_stats.total_searches - 总检索次数
 * @property {number} search_stats.avg_results - 平均结果数
 * @property {number} search_stats.zero_result_rate - 零结果率
 * @property {number} search_stats.avg_latency_ms - 平均延迟
 * @property {number} search_stats.p50_latency_ms - P50 延迟
 * @property {Object} rag_eval - RAGAS 评估信息
 * @property {number} test_cases_count - 测试用例数
 * @property {string} generated_at - 生成时间
 */

/**
 * @name SearchResponse
 * GET /api/search
 * @typedef {Object} SearchResponse
 * @property {SearchItem[]} wiki_results - Wiki 搜索结果
 * @property {SearchItem[]} chunk_results - Chunk 搜索结果
 * @property {string} [wiki_recommend] - Wiki 推荐
 * @property {string} [reflection] - 图上下文反思
 * @property {number} total - 总结果数
 * @property {number} page - 当前页
 * @property {number} page_size - 每页大小
 * 
 * @typedef {Object} SearchItem
 * @property {string} text - 文档内容
 * @property {number} score - 相关性分数
 * @property {string} file_name - 源文件名
 * @property {number} chunk_index - 块索引
 * @property {string} [_source] - 来源类型 (wiki/doc/table_view)
 * @property {number} [_weighted_score] - 加权分数
 */

/**
 * @name FeedbackResponse
 * GET /api/feedback/weekly
 * @typedef {Object} FeedbackResponse
 * @property {Array<FeedbackItem>} feedbacks - 反馈列表
 * @property {string} message - 提示消息
 * 
 * @typedef {Object} FeedbackItem
 * @property {string} timestamp - 时间戳
 * @property {string} query - 用户查询
 * @property {number} rating - 评分
 * @property {string} feedback - 反馈内容
 */

/**
 * @name FeatureFlagsResponse
 * GET /api/feature-flags
 * @typedef {Object} FeatureFlagsResponse
 * @property {Object<string,boolean>} flags - 功能开关映射
 * @property {Object<string,boolean>} defaults - 默认值
 */

/**
 * @name ChatResponse
 * POST /api/chat
 * @typedef {Object} ChatResponse
 * @property {string} answer - AI 回答内容
 * @property {Array} [sources] - 引用来源
 * @property {string} [reflection] - 反思信息
 */
