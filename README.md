[![ Logo OpenStudioLandscapes ](https://github.com/michimussato/OpenStudioLandscapes/raw/main/_images/logo128.png)](https://github.com/michimussato/OpenStudioLandscapes)

---

<!-- TOC -->
* [OpenStudioLandscapes Feature Template](#openstudiolandscapes-feature-template)
  * [Guide: How to use the Feature Template](#guide-how-to-use-the-feature-template)
* [First Install](#first-install)
* [File De-Duplication (Hard-Links)](#file-de-duplication-hard-links)
<!-- TOC -->

---

# OpenStudioLandscapes Feature Template

Source template version: [`3.0.2`](https://github.com/michimussato/OpenStudioLandscapes-Template/tree/3.0.2)

## Guide: How to use the Feature Template

1. Create your new Git repo on Github, 
   i.e. `yourlogin/OpenStudioLandscapes-YourFeature`.
   We could do that programmatically with [`gh`](https://cli.github.com/manual/gh_api):
   ```shell
   gh repo create yourlogin/OpenStudioLandscapes-YourFeature --push --disable-issues --disable-wiki --internal --source ./OpenStudioLandscapes-YourFeature --remote=upstream
   ```
2. Clone OpenStudioLandscapes-Template
   ```shell
   cd .features
   git clone https://github.com/michimussato/OpenStudioLandscapes-Template.git OpenStudioLandscapes-Your-New-Feature
   ```
3. Rename Git remote
   1. ```shell
      cd OpenStudioLandscapes-Your-New-Feature
      # Just to make sure we start clean
      rm -rf .venv
      rm -rf .idea
      rm -rf .git && git init --initial-branch=main
      ```
   2. Rename src directory
      ```shell
      mv src/OpenStudioLandscapes/Template src/OpenStudioLandscapes/Your_New_Feature
      ```
   3. ```shell
      git remote add origin https://github.com/yourlogin/OpenStudioLandscapes-Your-New-Feature.git
      git branch -M main
      ```
   4. Create initial commit
      ```shell
      git add --all
      git commit -m "initial commit"
      ```
   5. Initial Push
      ```shell
      git push -u origin main
      ```
4. Rename Template
   # 1. OpenStudioLandscapes-Template -> OpenStudioLandscapes-Your-New-Feature
   #    - `mv OpenStudioTemplates-Temkplate OpenStudioLandscapes-Your-New-Feature`
   2. All occurrences of `<Your-New-Feature>` -> `Your-Feature`
      - `Ctrl+Shift+R` in PyCharm
      - `find . -type f | xargs sed -i 's/<Your-New-Feature>/Your-Feature/g'`
   3. All occurrences of `<Your_New_Feature>` -> `Your_Feature`
      - `Ctrl+Shift+R` in PyCharm
      - `find . -type f | xargs sed -i 's/<Your_New_Feature>/Your_Feature/g'`
   4. All occurrences of `John Doe` -> `Your Name`
      - `Ctrl+Shift+R` in PyCharm
      - `find . -type f | xargs sed -i 's/John Doe/Your Name/g'`
   5. All occurrences of `john.doe@acme.com` -> `your.name@email.com`
      - `Ctrl+Shift+R` in PyCharm
      - `find . -type f | xargs sed -i 's/john.doe@acme.com/your.name@email.com/g'`
   6. All occurrences of `20XX` -> `2025`
      - `Ctrl+Shift+R` in PyCharm
      - `find . -type f | xargs sed -i 's/20XX/$(date +%Y)/g'`
   7. All occurrences of `YourLogin` -> `your_github_login`
      - `Ctrl+Shift+R` in PyCharm
      - `find . -type f | xargs sed -i 's/YourLogin/your_github_login/g'`
   8. All occurrences of `GROUP = "Template"` -> `GROUP = "Your_New_Feature"`
      - `Ctrl+Shift+R` in PyCharm
      - `find . -type f | xargs sed -i 's/GROUP = "Your_New_Feature"/GROUP = "Your_New_Feature"/g'`
   9. All occurrences of `<USERNAME>` -> `your_github_login`
      - `Ctrl+Shift+R` in PyCharm
      - `find . -type f | xargs sed -i 's/<USERNAME>/your_github_login/g'`
   10. All occurrences of `"compose_Your_New_Feature"` -> `"compose_your_new_feature"`
       - `Ctrl+Shift+R` in PyCharm
       - `find . -type f | xargs sed -i 's/"compose_Your_New_Feature"/"compose_Your_New_Feature"/g'`
   10. All occurrences of `compose_template` -> `compose_your_new_feature`
       - `Ctrl+Shift+R` in PyCharm
       - `find . -type f | xargs sed -i 's/compose_template/compose_your_new_feature/g'`
   11. All occurrences of `service_name = "Your_New_Feature"` -> `service_name = "Your_New_Feature"`
       - `Ctrl+Shift+R` in PyCharm
       - `find . -type f | xargs sed -i 's/service_name = "Your_New_Feature"/service_name = "Your_New_Feature"/g'`
   12. Revert `README.md`
       - `git checkout -f README.md`
   13. Commit changes
       ```shell
       git add --all
       git commit -m "Initial Changes"
       ```
   14. Initial Push
       ```shell
       git push -u origin main
       ```

# First Install

Add the following code to `OpenStudioLandscapes.engine.constants` (`THIRD_PARTY`):

```python
THIRD_PARTY.append
    {
        "enabled": True,
        "module": "OpenStudioLandscapes.Your_New_Feature.definitions",
        "compose_scope": ComposeScope.DEFAULT,
    }
```

Install `OpenStudioLandscapes-Your-New-Feature` into
`OpenStudioLandscapes/.venv`

```shell
source ../../.venv/bin/activate
pip install -e ".[dev]"
```

Basic installation instructions will be generated automatically. 
Once all preliminary steps were executed, the following command will generate
the new `READMD.md` for `Your-New-Feature`:

```shell
nox --session readme
```

# File De-Duplication (Hard-Links)

See [OpenStudioLandscapes README](https://github.com/michimussato/OpenStudioLandscapes#hard-links-sync-files-and-directories-across-repositories-de-duplication)
