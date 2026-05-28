local function va(...)
  local x = debug.getlocal(1, -1)
  return x
end
local n = 0
debug.sethook(function() n = n + 1 end, "l")
local y = va(42)
debug.sethook()
return tostring(y) .. ":" .. n
