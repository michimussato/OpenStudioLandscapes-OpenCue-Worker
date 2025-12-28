import textwrap

import snakemd


def readme_feature(
    doc: snakemd.Document,
    main_header: str,
) -> snakemd.Document:

    # Some Specific information

    doc.add_heading(
        text=main_header,
        level=1,
    )

    # Logo

    doc.add_paragraph(
        snakemd.Inline(
            text=textwrap.dedent(
                """\
                Logo OpenCue\
                """
            ),
            image="https://docs.opencue.io/assets/images/opencue_logo_with_text.png",
            link="https://www.opencue.io/",
        ).__str__()
    )

    doc.add_paragraph(
        text=textwrap.dedent(
            """\
            For more information about this Feature, visit the
            main resource:\
            """
        )
    )

    doc.add_unordered_list(
        [
            "[OpenStudioLandscapes-OpenCue](https://github.com/michimussato/OpenStudioLandscapes-OpenCue)",
        ]
    )

    doc.add_horizontal_rule()

    return doc


if __name__ == "__main__":
    pass
