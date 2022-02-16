import re

import yaml

from .utils import optimized_diff_match_patch

tofu_lower_limit = 200000
tofu_upper_limit = 1112064


def get_diffs(text1, text2):
    """Compute diff between source and target with DMP.

    Args:
        source (str): source text
        target (str): target text
    Returns:
        list: list of diffs
    """
    print("[INFO] Computing diffs ...")
    dmp = optimized_diff_match_patch()
    diffs = dmp.diff_main(text1, text2)
    print("[INFO] Diff computed!")
    return diffs


def to_yaml(
    list_,
):
    """Dump list to yaml and write the yaml to a file on mentioned path.

    Args:
        list_ (list): list
        vol_path (path): base path object
    """
    list_yaml = yaml.safe_dump(list_, allow_unicode=True)

    return list_yaml


def from_yaml(path):
    """Load yaml to list.

    Args:
        vol_path (path): base path object
        type (string):
    """
    diffs = yaml.safe_load(path.read_text(encoding="utf-8"))
    diffs_list = list(diffs)
    return diffs_list


def to_text(diffs):
    """Diff type of non -1 will be appended to generate a text which contains transfered annotations.

    Args:
        diffs (list): list diff tuples containing diff type and diff value

    Returns:
        str: annotation transferd text
    """
    result = ""
    for diff in diffs:
        if diff[0] != -1:
            result += diff[1]
    return result


def tag_to_tofu(content, annotations):
    """Annotations found in content will be converted to tofu id.

    It will help to generate cleaner diffs.A dictionionary is created to save annotation
    and its assigned tofu id in order to reconstruct new content.

    Args:
        content (str): content can be source as well as target.
        annotations (list): list of annotation that needs to be converted into tofu id.

    Returns:
        str: new content containing tofu id in place of annotations.
        dict: tofu id as key and annotation as value.
    """
    print("Mapping annotations to tofu-IDs")
    new_content = content
    #  support
    if isinstance(annotations[0], str):
        annotations = [annotations]

    tofu_mapping = {}
    tofu_walker = 0
    for annotation in annotations:
        split_list = re.split(annotation[1], new_content)
        for i, e in enumerate(split_list):
            if re.search(annotation[1], e):
                tofu = chr(tofu_walker + tofu_lower_limit)
                tofu_walker += 1
                tofu_mapping[tofu] = [annotation[0], e]
                split_list[i] = tofu
        new_content = "".join(split_list)
    return new_content, tofu_mapping


def filter_diff(diffs_list, tofu_mapping):
    """Filter the diffs by accepting the diff text belonging to pattern.

    Args:
        diffs_list (list): list of tuple containing diff type and diff text
        tofu_mapping (dit): dictionary containing key as tofu id and value as annotation info

    Returns:
        list: filtered diff list
    """
    print("Transfering annotations...")
    result = []
    for i, (diff_type, diff_text) in enumerate(diffs_list):
        if diff_type == 0 or diff_type == 1:
            result.append([diff_type, diff_text, ""])
        elif diff_type == -1:
            # tofu-IDs are limited to 1114111
            if re.search(
                f"[{chr(tofu_lower_limit)}-{chr(tofu_upper_limit)}]", diff_text
            ):
                anns = re.split(
                    f"([{chr(tofu_lower_limit)}-{chr(tofu_upper_limit)}])", diff_text
                )
                for ann in anns:
                    if ann:
                        if tofu_mapping.get(ann):
                            tag, value = tofu_mapping.get(ann)
                            result.append([0, value, tag])
                        else:
                            result.append([-1, ann, ""])
    return result


def transfer(source, patterns, target, output="txt"):
    """Extract annotations from with regex patterns and transfer to target.

    Arguments:
        source {str} -- text version containing the annotations to transfer
        patterns {list} -- ['annotation type', '(regex to detect the annotations)'] Put in () to preserve, without to delete.
        target {str} -- text that will receive the transfered annotation

    Keyword Arguments:
        output {str} -- ["diff", "yaml" or "txt"] (default: {'diff'})
        optimized {bool} -- whether to used node for dmp (default: {True})

    Returns:
        [diff, yaml or txt] -- returns a diff with 3 types of strings: 0 overlaps, 1 target and -1 source.
        Can also return the diff in yaml or a string containing target+annotations
    """
    print(f"Annotation transfer started...")
    tofu_source, tofu_mapping = tag_to_tofu(source, patterns)
    diffs = get_diffs(tofu_source, target)

    filterred_diff = filter_diff(diffs, tofu_mapping)

    if output == "diff":
        result = filterred_diff
    elif output == "yaml":
        result = to_yaml(filterred_diff)
    elif output == "txt":
        result = to_text(filterred_diff)
    return result