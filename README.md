# Setup: Custom pyRevit Extension on Revit 2024

## 1. Install pyRevit

Open **Application Workspace** → install **pyRevit**. Launch Revit 2024 and confirm a **pyRevit** tab appears on the ribbon.

## 2. Set up the custom folder
 
Create this structure anywhere stable (e.g., `C:\pyRevitCustom`):
 
```
C:\pyRevitCustom\
└── MyTools.extension\
    └── Custom.tab\
        └── Family.panel\
            └── BuildDoor.pushbutton\
                └── script.py
```

Naming rules are strict — folders must end in `.extension`, `.tab`, `.panel`, `.pushbutton`. The name *before* the suffix is what shows in the ribbon.

## 3. Connect the folder to Revit

In Revit:

1. **pyRevit tab** → dropdown under big pyRevit button → **Settings**
2. **Custom Extension Directories** → **Add Folder** → select `C:\pyRevitCustom`
3. **Save Settings and Reload**

> Pick the **parent** folder (`C:\pyRevitCustom`), NOT the `.extension` folder itself. This is the #1 setup failure.

A new **Custom** tab with a **BuildDoor** button appears on the ribbon.

---

## Day-to-day

- Edit `script.py` → next button click runs new code (no reload needed).
- Add new pushbutton folders → pyRevit dropdown → **Reload**.
- Don't put custom code inside `C:\Program Files\pyRevit-Master\` — it gets wiped on pyRevit updates.