# Contributing

We welcome contributions from new features to suggestions for improvement. Here are a few guildlines we would like you to follow in different situations:

## Found a Bug

If you encounter a bug, you can raise an issue in our [GitHub repository](https://github.com/mrtan-ys/RoleML). If you already have an idea how to fix it, we encourage you to submit a pull request for your contribution.

## Requesting a Feature

Before asking for a new feature, please check if it is already implemented in the latest version, or there is already a similar request or an ongoing pull request in our [GitHub repository](https://github.com/mrtan-ys/RoleML). If not, feel free to raise an issue describing your needs.

If you are looking for a small feature and are ready for coding, simply go ahead and submit a pull request once you are done.

## Raising a General Question

As a growing project, we also welcome any general discussion on the system using GitHub issues. If you have a new question, it is usually better to raise an issue than sending an email to one of the authors/maintainers because it would prevent others who have similar questions from seeing the discussions. Please be friendly throughout the discussions.

Please try to speak in English whenever possible. Otherwise we may need to paraphrase your question in English before responding to it.

## Contributing Source Code

If you would like to contribute to RoleML's source code repository, make sure to follow some general standards adopted by the open-source community:

* Follow _[conventional commit](https://www.conventionalcommits.org/en/v1.0.0/)_ for organizing the contents of each commit and writing commit messages. As an addition, you can use the `chore` commit type for miscellaneous commits that do not suit any predefined type (e.g., updating package dependency versions).
* Follow _[PEP 8](https://peps.python.org/pep-0008/)_ when writing Python code. As an exception, we allow a maximum line width of 100 characters in normal cases.

Before writing your code, please fork the original repository and create a branch from `main`. To improve readability, the name of the new branch should be `<type>/<desc>`, where `type` should match one of the conventional commit types and `desc` a high-level summary of the contribution (words should be separated by hyphens `-`).

Please try your best to control the amount of code in a single commit. The rule of thumb is that there should be no more than 300 lines of manually-written code per commit. If you are in doubt whether the development is in a proper direction, you can also submit a pull request in advance so that we can have a discussion.

After completing the development, please submit a pull request for code review.
