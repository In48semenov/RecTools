#  Copyright 2022 MTS (Mobile Telesystems)
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Classification recommendations metrics."""

import typing as tp
from collections import defaultdict

import attr
import numpy as np
import pandas as pd

from rectools import Columns

from .base import Catalog, DebiasMetric, MetricAtK, merge_reco

TP = "__TP"
FP = "__FP"
FN = "__FN"
TN = "__TN"
LIKED = "__LIKED"


@attr.s
class ClassificationMetric(MetricAtK):
    """
    Classification metric base class.

    Warning: This class should not be used directly.
    Use derived classes instead.

    Parameters
    ----------
    k : int
        Number of items at the top of recommendations list that will be used to calculate metric.
    """

    def calc(self, reco: pd.DataFrame, interactions: pd.DataFrame, catalog: Catalog) -> float:
        """
        Calculate metric value.

        Parameters
        ----------
        reco : pd.DataFrame
            Recommendations table with columns `Columns.User`, `Columns.Item`, `Columns.Rank`.
        interactions : pd.DataFrame
            Interactions table with columns `Columns.User`, `Columns.Item`.
        catalog : collection
            Collection of unique item ids that could be used for recommendations.

        Returns
        -------
        float
            Value of metric (average between users).
        """
        per_user = self.calc_per_user(reco, interactions, catalog)
        return per_user.mean()

    def calc_per_user(self, reco: pd.DataFrame, interactions: pd.DataFrame, catalog: Catalog) -> pd.Series:
        """
        Calculate metric values for all users.

        Parameters
        ----------
        reco : pd.DataFrame
            Recommendations table with columns `Columns.User`, `Columns.Item`, `Columns.Rank`.
        interactions : pd.DataFrame
            Interactions table with columns `Columns.User`, `Columns.Item`.
        catalog : collection
            Collection of unique item ids that could be used for recommendations.

        Returns
        -------
        pd.Series
            Values of metric (index - user id, values - metric value for every user).
        """
        self._check(reco, interactions=interactions)
        confusion_df = make_confusions(reco, interactions, self.k)
        return self.calc_per_user_from_confusion_df(confusion_df, catalog)

    def calc_from_confusion_df(self, confusion_df: pd.DataFrame, catalog: Catalog) -> float:
        """
        Calculate metric value from prepared confusion matrix.

        Parameters
        ----------
        confusion_df : pd.DataFrame
            Table with some confusion values for every user.
            Columns are: `Columns.User`, `LIKED`, `TP`, `FP`, `FN`.
            This table can be generated by `make_confusions` (or `calc_confusions`) function.
            See its description for details.
        catalog : collection
            Collection of unique item ids that could be used for recommendations.

        Returns
        -------
        float
            Value of metric (average between users).
        """
        per_user = self.calc_per_user_from_confusion_df(confusion_df, catalog)
        return per_user.mean()

    def calc_per_user_from_confusion_df(self, confusion_df: pd.DataFrame, catalog: Catalog) -> pd.Series:
        """
        Calculate metric values for all users from prepared confusion matrix.

        Parameters
        ----------
        confusion_df : pd.DataFrame
            Table with some confusion values for every user.
            Columns are: `Columns.User`, `LIKED`, `TP`, `FP`, `FN`.
            This table can be generated by `make_confusions` (or `calc_confusions`) function.
            See its description for details.
        catalog : collection
            Collection of unique item ids that could be used for recommendations.

        Returns
        -------
        pd.Series
            Values of metric (index - user id, values - metric value for every user).
        """
        if TN not in confusion_df:
            confusion_df[TN] = len(catalog) - self.k - confusion_df[FN]
        return self._calc_per_user_from_confusion_df(confusion_df, catalog).rename(None)

    def _calc_per_user_from_confusion_df(self, confusion_df: pd.DataFrame, catalog: Catalog) -> pd.Series:
        raise NotImplementedError()


@attr.s
class SimpleClassificationMetric(MetricAtK):
    """
    Simple classification metric base class.

    Warning: This class should not be used directly.
    Use derived classes instead.

    Parameters
    ----------
    k : int
        Number of items at the top of recommendations list that will be used to calculate metric.
    """

    def calc(self, reco: pd.DataFrame, interactions: pd.DataFrame) -> float:
        """
        Calculate metric value.

        Parameters
        ----------
        reco : pd.DataFrame
            Recommendations table with columns `Columns.User`, `Columns.Item`, `Columns.Rank`.
        interactions : pd.DataFrame
            Interactions table with columns `Columns.User`, `Columns.Item`.

        Returns
        -------
        float
            Value of metric (average between users).
        """
        per_user = self.calc_per_user(reco, interactions)
        return per_user.mean()

    def calc_per_user(self, reco: pd.DataFrame, interactions: pd.DataFrame) -> pd.Series:
        """
        Calculate metric values for all users.

        Parameters
        ----------
        reco : pd.DataFrame
            Recommendations table with columns `Columns.User`, `Columns.Item`, `Columns.Rank`.
        interactions : pd.DataFrame
            Interactions table with columns `Columns.User`, `Columns.Item`.

        Returns
        -------
        pd.Series
            Values of metric (index - user id, values - metric value for every user).
        """
        self._check(reco, interactions=interactions)
        confusion_df = make_confusions(reco, interactions, self.k)
        return self.calc_per_user_from_confusion_df(confusion_df)

    def calc_from_confusion_df(self, confusion_df: pd.DataFrame) -> float:
        """
        Calculate metric value from prepared confusion matrix.

        Parameters
        ----------
        confusion_df : pd.DataFrame
            Table with some confusion values for every user.
            Columns are: `Columns.User`, `LIKED`, `TP`, `FP`, `FN`.
            This table can be generated by `make_confusions` (or `calc_confusions`) function.
            See its description for details.

        Returns
        -------
        float
            Value of metric (average between users).
        """
        per_user = self.calc_per_user_from_confusion_df(confusion_df)
        return per_user.mean()

    def calc_per_user_from_confusion_df(self, confusion_df: pd.DataFrame) -> pd.Series:
        """
        Calculate metric values for all users from prepared confusion matrix.

        Parameters
        ----------
        confusion_df : pd.DataFrame
            Table with some confusion values for every user.
            Columns are: `Columns.User`, `LIKED`, `TP`, `FP`, `FN`.
            This table can be generated by `make_confusions` (or `calc_confusions`) function.
            See its description for details.

        Returns
        -------
        pd.Series
            Values of metric (index - user id, values - metric value for every user).
        """
        return self._calc_per_user_from_confusion_df(confusion_df).rename(None)

    def _calc_per_user_from_confusion_df(self, confusion_df: pd.DataFrame) -> pd.Series:
        raise NotImplementedError()


@attr.s
class Precision(SimpleClassificationMetric):
    """
    Ratio of relevant items among top-`k` recommended items.

    The precision@k equals to ``tp / k``
    where ``tp`` is the number of relevant recommendations
    among first ``k`` items in the top of recommendation list.

    Parameters
    ----------
    k : int
        Number of items in top of recommendations list that will be used to calculate metric.
    """

    def _calc_per_user_from_confusion_df(self, confusion_df: pd.DataFrame) -> pd.Series:
        return confusion_df[TP] / self.k


@attr.s
class Recall(SimpleClassificationMetric):
    """
    Ratio of relevant recommended items among all items user interacted with
    after recommendations were made.

    The recall@k equals to ``tp / liked`` where
        - ``tp`` is the number of relevant recommendations
          among first ``k`` items in the top of recommendation list;
        - ``liked`` is the number of items the user has interacted
          (bought, liked) with (in period after recommendations were given).

    Parameters
    ----------
    k : int
        Number of items in top of recommendations list that will be used to calculate metric.
    """

    def _calc_per_user_from_confusion_df(self, confusion_df: pd.DataFrame) -> pd.Series:
        return confusion_df[TP] / confusion_df[LIKED]


@attr.s
class Accuracy(ClassificationMetric):
    """
    Ratio of correctly recommended items among all items.

    The accuracy@k equals to ``(tp + tn) / n_items`` where
        - ``tp`` is the number of relevant recommendations
          among the first ``k`` items in recommendation list;
        - ``tn`` is the number of items with which user has not interacted (bought, liked) with
          (in period after recommendations were given) and we do not recommend to him
          (in the top ``k`` items of recommendation list);
        - ``n_items`` - an overall number of items that could be used for recommendations.

    Parameters
    ----------
    k : int
        Number of items at the top of recommendations list that will be used to calculate metric.
    """

    def _calc_per_user_from_confusion_df(self, confusion_df: pd.DataFrame, catalog: Catalog) -> pd.Series:
        accuracy = (confusion_df[TP] + confusion_df[TN]) / len(catalog)
        return accuracy


@attr.s
class F1Beta(SimpleClassificationMetric):
    """
    Fbeta score for k first recommendations.
    See more: https://en.wikipedia.org/wiki/F-score

    The f1_beta equals to ``(1 + beta_sqr) * p@k * r@k / (beta_sqr * p@k + r@k)``
    where
        - beta_sqr equals to beta ** 2
        - p@k: precision@k equals to ``tp / k`` where
            -``tp`` is the number of relevant recommendations
                among first ``k`` items in the top of recommendation list.
        - r@k: recall@k equals to ``tp / liked`` where
            - ``tp`` is the number of relevant recommendations
                among first ``k`` items in the top of recommendation list;
            - ``liked`` is the number of items the user has interacted
                (bought, liked) with (in period after recommendations were given).

    Parameters
    ----------
    k : int
        Number of items in top of recommendations list that will be used to calculate metric.
    beta : float
        Weight of recall. Default value: beta = 1.0
    """

    beta: float = attr.ib(default=1.0)

    def _calc_per_user_from_confusion_df(self, confusion_df: pd.DataFrame) -> pd.Series:
        beta_sqr = self.beta**2
        p_k = confusion_df[TP] / self.k
        r_k = confusion_df[TP] / confusion_df[LIKED]

        f1 = (1 + beta_sqr) * p_k * r_k / (beta_sqr * p_k + r_k)
        f1.loc[(p_k == 0.0) & (r_k == 0.0)] = 0.0
        return f1


@attr.s
class MCC(ClassificationMetric):
    """
    Matthew correlation coefficient calculates correlation between actual and predicted classification.
    Min value = -1 (negative correlation), Max value = 1 (positive correlation), zero means no correlation
    See more: https://en.wikipedia.org/wiki/Phi_coefficient

    The MCC equals to ``(tp * tn - fp * fn) / sqrt((tp + fp)(tp + fn)(tn + fp)(tn + fn))`` where
        - ``tp`` is the number of relevant recommendations
          among the first ``k`` items in recommendation list;
        - ``tn`` is the number of items with which user has not interacted (bought, liked) with
          (in period after recommendations were given) and we do not recommend to him
          (in the top ``k`` items of recommendation list);
        - ``fp`` - number of non-relevant recommendations among the first `k` items of recommendation list;
        - ``fn`` - number of items the user has interacted with but that weren't recommended (in top-`k`).

    Parameters
    ----------
    k : int
        Number of items in top of recommendations list that will be used to calculate metric.
    """

    def _calc_per_user_from_confusion_df(self, confusion_df: pd.DataFrame, catalog: Catalog) -> pd.Series:
        tp_ = confusion_df[TP]
        tn_ = confusion_df[TN]
        fp_ = confusion_df[FP]
        fn_ = confusion_df[FN]
        mcc_numerator = tp_ * tn_ - fp_ * fn_
        mcc_denominator = np.sqrt((tp_ + fp_) * (tp_ + fn_) * (tn_ + fp_) * (tn_ + fn_))
        mcc = mcc_numerator / mcc_denominator
        mcc.loc[mcc_denominator == 0.0] = 0.0  # if denominator == 0 than numerator is also equals 0
        return mcc


@attr.s
class DebiasPrecision(Precision, DebiasMetric):
    """
    Debias Ratio of relevant items among top-`k` recommended items.

    Parameters
    ----------
    k : int
        Number of items at the top of recommendations list that will be used to calculate metric.
    iqr_coef : float, default 1.5
        Coefficient for defining as the maximum value inside the border.
    random_state : float, default 32
        Pseudorandom number generator state to control the down-sampling.
    """

    def calc_per_user(self, reco: pd.DataFrame, interactions: pd.DataFrame) -> pd.Series:
        """
        Calculate metric values for all users with using downsampling for popularity items.

        Parameters
        ----------
        reco : pd.DataFrame
            Recommendations table with columns `Columns.User`, `Columns.Item`, `Columns.Rank`.
        interactions : pd.DataFrame
            Interactions table with columns `Columns.User`, `Columns.Item`.

        Returns
        -------
        pd.Series
            Values of metric (index - user id, values - metric value for every user).
        """
        interactions_wo_popularity = self.make_downsample(interactions)
        return super().calc_per_user(reco=reco, interactions=interactions_wo_popularity)


@attr.s
class DebiasRecall(Recall, DebiasMetric):
    """
    Debias Ratio of relevant recommended items among all items user interacted with
    after recommendations were made.

    Parameters
    ----------
    k : int
        Number of items at the top of recommendations list that will be used to calculate metric.
    iqr_coef : float, default 1.5
        Coefficient for defining as the maximum value inside the border.
    random_state : float, default 32
        Pseudorandom number generator state to control the down-sampling.
    """

    def calc_per_user(self, reco: pd.DataFrame, interactions: pd.DataFrame) -> pd.Series:
        """
        Calculate metric values for all users with using downsampling for popularity items.

        Parameters
        ----------
        reco : pd.DataFrame
            Recommendations table with columns `Columns.User`, `Columns.Item`, `Columns.Rank`.
        interactions : pd.DataFrame
            Interactions table with columns `Columns.User`, `Columns.Item`.

        Returns
        -------
        pd.Series
            Values of metric (index - user id, values - metric value for every user).
        """
        interactions_wo_popularity = self.make_downsample(interactions)
        return super().calc_per_user(reco=reco, interactions=interactions_wo_popularity)


@attr.s
class DebiasF1Beta(F1Beta, DebiasMetric):
    """
    Debias Fbeta score for k first recommendations.

    Parameters
    ----------
    k : int
        Number of items at the top of recommendations list that will be used to calculate metric.
    beta : float
        Weight of recall. Default value: beta = 1.0
    iqr_coef : float, default 1.5
        Coefficient for defining as the maximum value inside the border.
    random_state : float, default 32
        Pseudorandom number generator state to control the down-sampling.
    """

    def calc_per_user(self, reco: pd.DataFrame, interactions: pd.DataFrame) -> pd.Series:
        """
        Calculate metric values for all users with using downsampling for popularity items.

        Parameters
        ----------
        reco : pd.DataFrame
            Recommendations table with columns `Columns.User`, `Columns.Item`, `Columns.Rank`.
        interactions : pd.DataFrame
            Interactions table with columns `Columns.User`, `Columns.Item`.

        Returns
        -------
        pd.Series
            Values of metric (index - user id, values - metric value for every user).
        """
        interactions_wo_popularity = self.make_downsample(interactions)
        return super().calc_per_user(reco=reco, interactions=interactions_wo_popularity)


@attr.s
class DebiasAccuracy(Accuracy, DebiasMetric):
    """
    Debias Ratio of correctly recommended items among all items.

    Parameters
    ----------
    k : int
        Number of items at the top of recommendations list that will be used to calculate metric.
    iqr_coef : float, default 1.5
        Coefficient for defining as the maximum value inside the border.
    random_state : float, default 32
        Pseudorandom number generator state to control the down-sampling.
    """

    def calc_per_user(self, reco: pd.DataFrame, interactions: pd.DataFrame, catalog: Catalog) -> pd.Series:
        """
        Calculate metric values for all users with using downsampling for popularity items.

        Parameters
        ----------
        reco : pd.DataFrame
            Recommendations table with columns `Columns.User`, `Columns.Item`, `Columns.Rank`.
        interactions : pd.DataFrame
            Interactions table with columns `Columns.User`, `Columns.Item`.
        catalog : collection
            Collection of unique item ids that could be used for recommendations.

        Returns
        -------
        pd.Series
            Values of metric (index - user id, values - metric value for every user).
        """
        interactions_wo_popularity = self.make_downsample(interactions)
        return super().calc_per_user(reco=reco, interactions=interactions_wo_popularity, catalog=catalog)


@attr.s
class DebiasMCC(MCC, DebiasMetric):
    """
    Debias Matthew correlation coefficient calculates correlation between actual and predicted classification.

    Parameters
    ----------
    k : int
        Number of items at the top of recommendations list that will be used to calculate metric.
    iqr_coef : float, default 1.5
        Coefficient for defining as the maximum value inside the border.
    random_state : float, default 32
        Pseudorandom number generator state to control the down-sampling.
    """

    def calc_per_user(self, reco: pd.DataFrame, interactions: pd.DataFrame, catalog: Catalog) -> pd.Series:
        """
        Calculate metric values for all users with using downsampling for popularity items.

        Parameters
        ----------
        reco : pd.DataFrame
            Recommendations table with columns `Columns.User`, `Columns.Item`, `Columns.Rank`.
        interactions : pd.DataFrame
            Interactions table with columns `Columns.User`, `Columns.Item`.
        catalog : collection
            Collection of unique item ids that could be used for recommendations.

        Returns
        -------
        pd.Series
            Values of metric (index - user id, values - metric value for every user).
        """
        interactions_wo_popularity = self.make_downsample(interactions)
        return super().calc_per_user(reco=reco, interactions=interactions_wo_popularity, catalog=catalog)


DebiasClassificationMetric = tp.Union[DebiasAccuracy, DebiasMCC]
DebiasSimpleClassificationMetric = tp.Union[DebiasPrecision, DebiasRecall, DebiasF1Beta]


def calc_classification_metrics(
    metrics: tp.Dict[
        str,
        tp.Union[
            ClassificationMetric,
            SimpleClassificationMetric,
            DebiasClassificationMetric,
            DebiasSimpleClassificationMetric,
        ],
    ],
    merged: pd.DataFrame,
    catalog: tp.Optional[Catalog] = None,
) -> tp.Dict[str, float]:
    """
    Calculate any classification metrics.

    Works with prepared data.

    Warning: It is not recommended to use this function directly.
    Use `calc_metrics` instead.

    Parameters
    ----------
    metrics : dict(str -> (ClassificationMetric | SimpleClassificationMetric))
        Dict of metric objects to calculate,
        where key is a metric name and value is a metric object.
    merged : pd.DataFrame
        Result of merging recommendations and interactions tables.
        Can be obtained using `merge_reco` function.
    catalog : collection, optional
        Collection of unique item ids that could be used for recommendations.
        Obligatory only if `metrics` contains `ClassificationMetric` instances.

    Returns
    -------
    dict(str->float)
        Dictionary where keys are the same as keys in `metrics`
        and values are metric calculation results.

    Raises
    ------
    ValueError
        If `n_items` is not passed and `ClassificationMetric` is present in `metrics`.
    TypeError
        If unexpected metric is present in `metrics`.
    """
    k_map = defaultdict(list)
    for name, metric in metrics.items():
        k_map[metric.k].append(name)

    results = {}
    for k, k_metrics in k_map.items():

        for metric_name in k_metrics:
            metric = metrics[metric_name]

            if isinstance(metric, (DebiasPrecision, DebiasRecall, DebiasF1Beta, DebiasAccuracy, DebiasMCC)):
                merged_without_pop_bias = metric.make_downsample(merged)
                confusion_df = calc_confusions(merged_without_pop_bias, k)
            else:
                confusion_df = calc_confusions(merged, k)

            if isinstance(metric, SimpleClassificationMetric):
                res = metric.calc_from_confusion_df(confusion_df)
            elif isinstance(metric, ClassificationMetric):
                if catalog is None:
                    raise ValueError(f"For calculating '{metric.__class__.__name__}' it's necessary to set `catalog`")
                res = metric.calc_from_confusion_df(confusion_df, catalog)
            else:
                raise TypeError(f"Unexpected classification metric {metric}")
            results[metric_name] = res

    return results


def calc_confusions(merged: pd.DataFrame, k: int) -> pd.DataFrame:
    """
    Calculate some intermediate metrics from prepared data (it's a helper function).

    For each user (`Columns.User`) the following metrics are calculated:
        - `LIKED` - number of items the user has interacted (bought, liked) with;
        - `TP` - number of relevant recommendations among the first `k` items at the top of recommendation list;
        - `FP` - number of non-relevant recommendations among the first `k` items of recommendation list;
        - `FN` - number of items the user has interacted with but that weren't recommended (in top `k`).

    Parameters
    ----------
    merged : pd.DataFrame
        Result of merging recommendations and interactions tables.
        Can be obtained using `merge_reco` function.
    k : int
        Number of items at the top of recommendations list that will be used to calculate metric.

    Returns
    -------
    pd.DataFrame
        Table with columns: `Columns.User`, `LIKED`, `TP`, `FP`, `FN`.

    Notes
    -----
    left = all - K
    TP = sum(rank)
    FP = K - TP
    FN = liked - TP
    TN = all - K - FN = left - FN = left - liked + TP
    """
    confusion_df = merged.groupby(Columns.User)[Columns.Item].agg("size").rename(LIKED).to_frame()
    confusion_df[TP] = merged.eval(f"__is_hit = {Columns.Rank} <= @k").groupby(Columns.User)["__is_hit"].agg("sum")
    confusion_df[FP] = k - confusion_df[TP]
    confusion_df[FN] = confusion_df[LIKED] - confusion_df[TP]
    return confusion_df


def make_confusions(reco: pd.DataFrame, interactions: pd.DataFrame, k: int) -> pd.DataFrame:
    """
    Calculate some intermediate metrics from raw data (it's a helper function).

    For each user the following metrics are calculated:
        - `LIKED` - number of items the user has interacted (bought, liked) with;
        - `TP` - number of relevant recommendations among the first `k` items at the top of recommendation list;
        - `FP` - number of non-relevant recommendations among the first `k` items of recommendation list;
        - `FN` - number of items the user has interacted with but that weren't recommended (in top-`k`).

    Parameters
    ----------
    reco : pd.DataFrame
        Recommendations table with columns `Columns.User`, `Columns.Item`, `Columns.Rank`.
    interactions : pd.DataFrame
        Interactions table with columns `Columns.User`, `Columns.Item`.
    k : int
        Number of items at the top of recommendations list that will be used to calculate metric.

    Returns
    -------
    pd.DataFrame
        Table with columns: `Columns.User`, `LIKED`, `TP`, `FP`, `FN`.
    """
    merged = merge_reco(reco, interactions)
    confusion_df = calc_confusions(merged, k)
    return confusion_df
