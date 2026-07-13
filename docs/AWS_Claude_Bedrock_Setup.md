Summary

This document shows how to write your AWS credentials to your Windows user AWS credentials file and validate them for use with Bedrock/Claude extensions.

Steps

1) Run the setup script (recommended — prompts for keys):

```powershell
# runs interactively and prompts for keys
.\setup_aws_credentials.ps1
```

Or provide keys on the command line (note: command history will contain the secret):

```powershell
.\setup_aws_credentials.ps1 -AccessKey AKI... -SecretKey "yourSecretHere"
```

2) Test the profile using AWS CLI (install AWS CLI v2 if needed):

```powershell
aws sts get-caller-identity --profile survey_of_israel --region il-central-1
```

Expected result: JSON with your AWS account/ARN. If you see an error, check keys and region.

3) VS Code settings

- The workspace `.vscode/settings.json` was updated to set `AWS_PROFILE=survey_of_israel` and `AWS_REGION=il-central-1` in the integrated terminal environment.
- If the Claude extension has an explicit AWS profile/region setting, set it to `survey_of_israel` / `il-central-1`.

Security notes

- Do NOT commit credentials into source control. The provided script writes directly to `%USERPROFILE%\\.aws\\credentials` and does not store secrets in the repo unless you pass them as CLI args.
- After setup, you may delete `setup_aws_credentials.ps1` if you prefer not to keep the helper in the repo.

If you want, I can:
- Run the `aws sts get-caller-identity` test for you (I need permission to run commands here).
- Add an automated check script that calls Bedrock or the Claude extension API (if you provide the extension's exact setting names).