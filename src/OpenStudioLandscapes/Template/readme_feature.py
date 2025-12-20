import textwrap

import snakemd


def readme_feature(doc: snakemd.Document) -> snakemd.Document:

    # Some Specific information

    # doc.add_heading(
    #     text="Official Resources",
    #     level=1,
    # )

    # Logo

    # doc.add_paragraph(
    #     snakemd.Inline(
    #         text=textwrap.dedent(
    #             """
    #             Logo Template
    #             """
    #         ),
    #         image={
    #             "Template": "https://www.url.com/yourlogo.png",
    #         }["Template"],
    #         link="https://www.url.com",
    #     ).__str__()
    # )
    #
    # doc.add_paragraph(
    #     text=textwrap.dedent(
    #         """
    #         Official Template information.
    #         """
    #     )
    # )

    ##################################################
    # TO EDIT THIS FILE FOR YOUR OWN FEATURE,
    # REMOVE EVERYTHING FROM HERE...

    doc.add_heading(
        text="Create new Feature from this Template",
        level=1,
    )

    # Logo

    doc.add_paragraph(
        snakemd.Inline(
            text=textwrap.dedent(
                """
                Logo OpenStudioLandscapes
                """
            ),
            image="https://github.com/michimussato/OpenStudioLandscapes/raw/main/media/images/logo128.png",
            link="https://www.url.com",
        ).__str__()
    )

    doc.add_heading(
        text="Create a new repository from this Template",
        level=2,
    )

    doc.add_paragraph(
        text=textwrap.dedent(
            """
            Click `Use this template` and select `Create a new repository`
            """
        )
    )

    doc.add_paragraph(
        snakemd.Inline(
            text=textwrap.dedent(
                """
                Create a new repository
                """
            ),
            image="media/images/use_template.png",
            # link="https://www.url.com",
        ).__str__()
    )

    doc.add_paragraph(
        text=textwrap.dedent(
            """
            And fill in information as needed by specifying the `Repository name *`
            of the OpenStudioLandscapes Feature (i.e. `OpenStudioLandscapes-NewFeature`):
            """
        )
    )

    doc.add_paragraph(
        snakemd.Inline(
            text=textwrap.dedent(
                """
                Create a new repository
                """
            ),
            image="media/images/create_repository.png",
            # link="https://www.url.com",
        ).__str__()
    )

    doc.add_heading(
        text="Clone new Feature to your local drive",
        level=2,
    )

    doc.add_paragraph(
        text=textwrap.dedent(
            """
            Clone the new Feature into the `.features` directory of your local
            `OpenStudioLandscapes` clone:
            """
        )
    )

    doc.add_code(
        code=textwrap.dedent(
            """\
            cd /to/your/git/repos/OpenStudioLandscapes/.features
            git clone <GIT_REPOSITORY_URL>\
"""
        )
    )

    doc.add_heading(
        text="Replace `Template` occurrences in `OpenStudioLandscapes-NewFeature`",
        level=2,
    )

    doc.add_paragraph(
        text=textwrap.dedent(
            """
            Rename the package directory from `Template` to `NewFeature`:
            """
        )
    )

    doc.add_code(
        code=textwrap.dedent(
            """\
            NEW_FEATURE="NewFeature"

            cd /to/your/git/repos/OpenStudioLandscapes/.features/OpenStudioLandscapes-${NEW_FEATURE}
            mv src/OpenStudioLandscapes/Template src/OpenStudioLandscapes/${NEW_FEATURE}\
"""
        )
    )

    doc.add_paragraph(
        text=textwrap.dedent(
            """
            Rename all occurrences of `template` in your new Feature with
            the correct name in the following files:
            """
        )
    )

    doc.add_unordered_list(
        [
            "update [`./pyproject.toml`](./pyproject.toml)",
            "update `./src/OpenStudioLandscapes/${NEW_FEATURE}/__init__.py`",
            "update `./src/OpenStudioLandscapes/${NEW_FEATURE}/assets.py`",
            "update `./src/OpenStudioLandscapes/${NEW_FEATURE}/constants.py`",
            "update `./src/OpenStudioLandscapes/${NEW_FEATURE}/definitions.py`",
            "update `./src/OpenStudioLandscapes/${NEW_FEATURE}/readme_feature.py` [`snakemd` Documentation](https://www.snakemd.io/en/latest/)",
            "remove media `rm ./media/images/*.*`",
            "remove nox reports `rm ./.nox/*.*`",
            "remove sbom reports `rm ./.sbom/*.*`",
        ]
    )

    doc.add_heading(
        text="Commit your initial Setup",
        level=2,
    )

    doc.add_paragraph(
        text=textwrap.dedent(
            """
            Commit all changes to Git:
            """
        )
    )

    doc.add_code(
        code=textwrap.dedent(
            """\
            git add *
            git commit -m "Initial Setup"
            git push\
"""
        )
    )

    doc.add_heading(
        text="Enable OpenStudioLandscapes-NewFeature in the Engine",
        level=2,
    )

    doc.add_paragraph(
        text=textwrap.dedent(
            """
            Commit all changes to Git:
            """
        )
    )

    doc.add_code(
        code=textwrap.dedent(
            """\
            cd /to/your/git/repos/OpenStudioLandscapes
            source .venv/bin/activate
            pip install --editable .features/OpenStudioLandscapes-${NEW_FEATURE}[dev]
            pip install --editable .[dev]\
"""
        )
    )

    doc.add_paragraph(
        text=textwrap.dedent(
            """
            Edit the `OpenStudioLandscapes.engine` to use
            your new Feature:
            """
        )
    )

    doc.add_unordered_list(
        [
            "update `OpenStudioLandscapes/.env`",
            "update `OpenStudioLandscapes/src/OpenStudioLandscapes/engine/features.py`",
            "update `OpenStudioLandscapes/README.md#current-feature-statuses`",
        ]
    )

    # ... TO HERE
    # AND USE THIS FILE TO HAVE YOUR OWN README.md
    # PROGRAMMATICALLY GENERATED.
    #
    # Help on snakemd:
    # https://www.snakemd.io/en/latest/
    ##################################################

    # doc.add_horizontal_rule()

    return doc


if __name__ == "__main__":
    pass
