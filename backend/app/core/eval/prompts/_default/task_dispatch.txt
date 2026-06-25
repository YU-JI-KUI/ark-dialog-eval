1. should_dispatch_to_bu:这个问题**该不该由本BU承接**?与本BU业务相关→true(该承接);与本BU无关(他业务/闲聊/拒识)→false(该拒识)。
   ★只依据"当前问题+多轮上下文(前文)",绝不能用"下一轮"反推(agent 当时还不知道用户下一轮会说什么)。在 dispatch_reason 写依据。
