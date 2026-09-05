#!/usr/bin/env python3
import re

new_files = [
    # (FileRefID, BuildFileRefID, FileName, GroupName, SubPath)
    ("002000", "002001", "Theme.swift", "DesignSystem", "AgentCoreIOS/DesignSystem/Theme.swift"),
    ("002002", "002003", "AgentOrbView.swift", "DesignSystem", "AgentCoreIOS/DesignSystem/AgentOrbView.swift"),
    ("002004", "002005", "AgentStatusPill.swift", "DesignSystem", "AgentCoreIOS/DesignSystem/AgentStatusPill.swift"),
    ("002006", "002007", "LocalIndicator.swift", "DesignSystem", "AgentCoreIOS/DesignSystem/LocalIndicator.swift"),
    ("002008", "002009", "ConnectionChip.swift", "DesignSystem", "AgentCoreIOS/DesignSystem/ConnectionChip.swift"),
    ("002010", "002011", "CustomComponents.swift", "DesignSystem", "AgentCoreIOS/DesignSystem/CustomComponents.swift"),
    ("002012", "002013", "AgentAppViewModel.swift", "ViewModels", "AgentCoreIOS/ViewModels/AgentAppViewModel.swift"),
    ("002014", "002015", "HomeView.swift", "Views", "AgentCoreIOS/Views/HomeView.swift"),
    ("002016", "002017", "ExecuteView.swift", "Views", "AgentCoreIOS/Views/ExecuteView.swift"),
    ("002018", "002019", "ActivityView.swift", "Views", "AgentCoreIOS/Views/ActivityView.swift"),
    ("002020", "002021", "VaultView.swift", "Views", "AgentCoreIOS/Views/VaultView.swift"),
    ("002022", "002023", "ConnectionsView.swift", "Views", "AgentCoreIOS/Views/ConnectionsView.swift"),
    ("002024", "002025", "SettingsView.swift", "Views", "AgentCoreIOS/Views/SettingsView.swift"),
    ("002026", "002027", "MainTabView.swift", "Views", "AgentCoreIOS/Views/MainTabView.swift"),
]

pbx_path = "ios/AgentCoreIOS.xcodeproj/project.pbxproj"
with open(pbx_path, "r") as f:
    content = f.read()

# 1. PBXBuildFile section
build_file_entries = "\n".join([
    f'\t\t{bf_id} /* {name} in Sources */ = {{isa = PBXBuildFile; fileRef = {fr_id} /* {name} */; }};'
    for fr_id, bf_id, name, _, _ in new_files
])
content = content.replace(
    "/* Begin PBXBuildFile section */",
    "/* Begin PBXBuildFile section */\n" + build_file_entries
)

# 2. PBXFileReference section
file_ref_entries = "\n".join([
    f'\t\t{fr_id} /* {name} */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = {name}; sourceTree = "<group>"; }};'
    for fr_id, _, name, _, _ in new_files
])
content = content.replace(
    "/* Begin PBXFileReference section */",
    "/* Begin PBXFileReference section */\n" + file_ref_entries
)

# 3. Create Groups for DesignSystem, ViewModels, Views inside AgentCoreIOS PBXGroup
design_system_refs = "\n".join([f'\t\t\t\t{fr_id} /* {name} */,' for fr_id, _, name, group, _ in new_files if group == "DesignSystem"])
viewmodels_refs = "\n".join([f'\t\t\t\t{fr_id} /* {name} */,' for fr_id, _, name, group, _ in new_files if group == "ViewModels"])
views_refs = "\n".join([f'\t\t\t\t{fr_id} /* {name} */,' for fr_id, _, name, group, _ in new_files if group == "Views"])

new_groups = f"""\t\t002030 /* DesignSystem */ = {{
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
{design_system_refs}
\t\t\t);
\t\t\tpath = DesignSystem;
\t\t\tsourceTree = "<group>";
\t\t}};
\t\t002031 /* ViewModels */ = {{
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
{viewmodels_refs}
\t\t\t);
\t\t\tpath = ViewModels;
\t\t\tsourceTree = "<group>";
\t\t}};
\t\t002032 /* Views */ = {{
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
{views_refs}
\t\t\t);
\t\t\tpath = Views;
\t\t\tsourceTree = "<group>";
\t\t}};"""

content = content.replace(
    "/* Begin PBXGroup section */",
    "/* Begin PBXGroup section */\n" + new_groups
)

# Add group references to AgentCoreIOS PBXGroup
agent_core_ios_group_children = "\t\t\t\t002030 /* DesignSystem */,\n\t\t\t\t002031 /* ViewModels */,\n\t\t\t\t002032 /* Views */,"
content = content.replace(
    "001071 /* AgentCoreIOS */ = {\n\t\t\tisa = PBXGroup;\n\t\t\tchildren = (",
    "001071 /* AgentCoreIOS */ = {\n\t\t\tisa = PBXGroup;\n\t\t\tchildren = (\n" + agent_core_ios_group_children
)

# 4. Add build files to Sources build phases (001090 for main target, 001091 for test target)
sources_main = "\n".join([f'\t\t\t\t{bf_id} /* {name} in Sources */,' for _, bf_id, name, _, _ in new_files])
content = content.replace(
    "001090 /* Sources */ = {\n\t\t\tisa = PBXSourcesBuildPhase;\n\t\t\tbuildActionMask = 2147483647;\n\t\t\tfiles = (",
    "001090 /* Sources */ = {\n\t\t\tisa = PBXSourcesBuildPhase;\n\t\t\tbuildActionMask = 2147483647;\n\t\t\tfiles = (\n" + sources_main
)

content = content.replace(
    "001091 /* Sources */ = {\n\t\t\tisa = PBXSourcesBuildPhase;\n\t\t\tbuildActionMask = 2147483647;\n\t\t\tfiles = (",
    "001091 /* Sources */ = {\n\t\t\tisa = PBXSourcesBuildPhase;\n\t\t\tbuildActionMask = 2147483647;\n\t\t\tfiles = (\n" + sources_main
)

with open(pbx_path, "w") as f:
    f.write(content)

print("Updated project.pbxproj successfully!")
