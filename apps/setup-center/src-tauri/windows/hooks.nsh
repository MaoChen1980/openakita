; OpenAkita Setup Center - NSIS Hooks
; 目标：
; - 卸载时强制杀掉残留进程（Setup Center 本体 + OpenAkita 后台服务）
; - 勾选“清理用户数据”时，删除用户目录下的 ~/.openakita

!macro _OpenAkita_KillPid pid
  StrCpy $0 "${pid}"
  ${If} $0 == ""
    Return
  ${EndIf}
  ; best-effort kill tree
  ExecWait 'taskkill /PID $0 /T /F' $1
!macroend

!macro _OpenAkita_KillAllServicePids
  ; ~/.openakita/run/openakita-*.pid
  ExpandEnvStrings $R0 "%USERPROFILE%\\.openakita\\run\\openakita-*.pid"
  FindFirst $R1 $R2 $R0
  ${DoWhile} $R2 != ""
    StrCpy $R3 "$R2"
    ; 读 pid
    FileOpen $R4 "$R1" "r"
    ${IfNot} ${Errors}
      FileRead $R4 $R5
      FileClose $R4
      ; $R5 可能带 \r\n
      StrCpy $R6 $R5 32
      ; kill
      !insertmacro _OpenAkita_KillPid $R6
    ${EndIf}
    ; next
    FindNext $R1 $R2
  ${Loop}
  FindClose $R1
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  ; 卸载前：强制杀掉残留进程，避免“卸载后仍在后台跑”
  ; 1) 杀掉 Setup Center（可能在托盘常驻）
  ExecWait 'taskkill /IM openakita-setup-center.exe /T /F' $0

  ; 2) 杀掉 OpenAkita serve（按 pid 文件枚举）
  !insertmacro _OpenAkita_KillAllServicePids
!macroend

!macro NSIS_HOOK_POSTUNINSTALL
  ; 勾选“清理用户数据”时：删除 ~/.openakita（真实用户数据目录）
  ; 仅在非更新模式下清理（与默认行为保持一致）
  ${If} $DeleteAppDataCheckboxState = 1
  ${AndIf} $UpdateMode <> 1
    ExpandEnvStrings $R0 "%USERPROFILE%\\.openakita"
    RmDir /r "$R0"
  ${EndIf}
!macroend

