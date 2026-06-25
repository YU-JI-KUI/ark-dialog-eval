【业务分类清单】
{intents}

【本轮对话】
  用户问题:{question}
  多轮上下文(含前文 AI 回答,当前问题若含"第二个/那个/换一个"等指代,回看上一轮 AI 答确定指向):
{ctx}
  AI回答(原始内容,可能是 JSON 渲染卡 / 含 HTML 标签 / 多层嵌套,请自行读懂其中对用户可见的语义,忽略标签和无关字段):
  {answer_text}
  紧接着用户的下一轮(仅用于评"是否解决",禁止用于判意图/分发):{next_user_turn}

  日志是否已把本条分给本BU:{dispatched_flag}

【任务】
{tasks}
只输出如下JSON,无任何多余文字:
{output_schema}
