from __future__ import annotations

DOMAIN_TERMS = {
    'government': ('政府','政务','管委会','党工委','市局','省厅','政策','领导汇报','数字政府','营商环境','审批服务局','政府部门','机关单位','机关'),
    'business': ('公司','企业','经营','部门','管理层','业务','董事会'),
    'data': ('数据','指标','同比','环比','趋势','分析','报表','经营分析','财务'),
    'technology': ('技术','架构','系统','平台','数据流','接口','部署','安全','数字化'),
    'product': ('产品','用户','功能','场景','解决方案'),
    'education': ('教学','学习','课程','课堂','培训','课件','知识','讲解','解读'),
    'sales': ('客户','投标','方案','销售','合作','招商','加盟','采购'),
    'marketing': ('品牌','活动','宣传','报名','传播','营销'),
    'startup': ('融资','投资人','bp','创业','路演'),
    'research': ('论文','研究','答辩','实验','学术'),
    'public': ('公众','演讲','分享','沙龙','公开课'),
    'personal': ('个人','简历','纪念','相册','求职'),
}

JOB_TERMS = {
    'report': ('汇报','总结','述职','复盘','报告','进展','完成情况'),
    'plan': ('规划','计划','方案','建设方案','路线图','实施方案','策划'),
    'decide': ('决策','拍板','批准','审批','请示','选择','预算','申请'),
    'explain': ('解释','讲解','解读','说明','科普','原理','介绍','知识'),
    'teach': ('培训','教学','课程','课堂','学习','课件'),
    'analyze': ('分析','趋势','同比','环比','诊断','原因','指标'),
    'persuade': ('说服','客户','价值','优势','选择我们','合作'),
    'pitch': ('路演','融资','评委','竞赛'),
    'speak': ('演讲','发言','讲话','分享'),
    'present': ('展示','介绍','宣传','品牌','个人介绍'),
    'defend': ('答辩','质疑','论文'),
    'promote': ('宣传','报名','活动','推广'),
    'review': ('复盘','年度总结','半年总结','季度总结','月度总结','工作总结','总结汇报'),
    'annual_review': ('年度总结','半年总结','年终总结','年度工作总结','半年工作总结','上半年工作总结','年度工作汇报','半年工作汇报'),
    'bid': ('投标','招标','评审专家','招标答辩','投标答辩'),
    'classroom': ('课堂','教师授课','学生','初中','高中','小学'),
    'assignment': ('课程作业','课堂作业','作业成果','作业汇报'),
    'proposal': ('商务提案','客户提案','咨询方案','方案提案','提案'),
}

SUPPRESS_PHRASES = {
    'speak': ('演讲者备注','speaker notes','speaker note','添加备注','备注和转场'),
}

NEGATORS = ('不是','不做','不讲','不需要','无需','不要','并非','非')


def positive_occurrences(text: str, term: str) -> int:
    """Count term occurrences outside a short explicit-negation scope.

    This is intentionally local, not a general Chinese parser. It prevents high-cost
    keyword inversions such as “不是招投标答辩” or “不讲系统架构” while keeping
    the router small and deterministic.
    """
    low = text.lower()
    needle = term.lower()
    if not needle:
        return 0
    count = 0
    start = 0
    while True:
        pos = low.find(needle, start)
        if pos < 0:
            break
        prefix = low[max(0, pos - 10):pos]
        # Negator must be in the local phrase immediately leading into the signal.
        negated = any(n in prefix for n in NEGATORS)
        if not negated:
            count += 1
        start = pos + max(1, len(needle))
    return count


def classify(text: str) -> dict:
    low = text.lower()
    domains = []
    jobs = []
    for key, terms in DOMAIN_TERMS.items():
        score = sum(positive_occurrences(low, t) for t in terms)
        if score:
            domains.append((key, score))
    for key, terms in JOB_TERMS.items():
        score = sum(positive_occurrences(low, t) for t in terms)
        for phrase in SUPPRESS_PHRASES.get(key, ()):
            if phrase.lower() in low:
                score = max(0, score - 2)
        if score:
            jobs.append((key, score))
    domains.sort(key=lambda x: (-x[1], x[0]))
    jobs.sort(key=lambda x: (-x[1], x[0]))
    return {
        'domains': [x[0] for x in domains[:3]],
        'jobs': [x[0] for x in jobs[:3]],
        'domain_scores': domains,
        'job_scores': jobs,
    }
