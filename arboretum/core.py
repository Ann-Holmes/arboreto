"""
Core functional building blocks, composed in a Dask graph for distributed computation.
"""

import numpy as np
import pandas as pd

from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor, ExtraTreesRegressor
from dask import delayed
from dask.dataframe import from_delayed
from dask.dataframe.utils import make_meta

THE_DEMON_SEED = 666

SKL_REGRESSOR_FACTORY = {
    'RF': RandomForestRegressor,
    'ET': ExtraTreesRegressor,
    'GBM': GradientBoostingRegressor
}

DEFAULT_KWARGS = {

    'RF': {
        'n_jobs': 1,
        'n_estimators': 1000,
        'max_features': 'sqrt'
    },

    'ET': {
        'n_jobs': 1,
        'n_estimators': 1000,
        'max_features': 'sqrt'
    },

    'GBM': {
        'learning_rate': 0.001,
        'n_estimators': 500,
        'max_features': 0.1
    },

    'XGB': {

    }

}


def __is_skl_regressor(regressor_type):
    """
    :param regressor_type: the regressor type to consider. Case insensitive.
    :return: boolean indicating whether the regressor type is a scikit-learn regressor.
    """
    return regressor_type.upper() in SKL_REGRESSOR_FACTORY.keys()


def __is_xgboost_regressor(regressor_type):
    """
    :param regressor_type: the regressor type to consider. Case insensitive.
    :return: boolean indicating whether the regressor type is the xgboost regressor.
    """
    return regressor_type.upper() == 'XGB'


def train_model(regressor_type,
                regressor_kwargs,
                tf_matrix,
                target_gene_expression,
                seed=THE_DEMON_SEED):
    """
    :param regressor_type: one of ['RF', 'ET', 'GBM', 'XGB']. Case insensitive.
    :param regressor_kwargs: a dict of key-value pairs that configures the regressor.
    :param tf_matrix: the predictor matrix (transcription factor matrix) as a numpy array.
    :param target_gene_expression: the target (y) gene expression to predict in function of the tf_matrix (X).
    :param seed: (optional) random seed for the regressors.
    :return: a trained regression model.
    """

    assert tf_matrix.shape[0] == len(target_gene_expression)

    if __is_skl_regressor(regressor_type):
        regressor = SKL_REGRESSOR_FACTORY[regressor_type](random_state=seed, **regressor_kwargs)

        regressor.fit(tf_matrix, target_gene_expression)

        return regressor

    elif __is_xgboost_regressor(regressor_type):
        raise ValueError('XGB regressor not yet supported')  # TODO

    else:
        raise ValueError('Unsupported regressor type: {0}'.format(regressor_type))


def to_tf_matrix(expression_matrix,
                 gene_names,
                 tf_names):
    """
    :param expression_matrix: numpy matrix. Rows are observations and columns are genes.
    :param gene_names: a list of gene names. Each entry corresponds to the expression_matrix column with same index.
    :param tf_names: a list of transcription factor names. Should be a subset of gene_names.
    :return: a numpy matrix representing the predictor matrix for the regressions.
    """

    assert expression_matrix.shape[1] == len(gene_names)

    tf_indices = [index for index, gene in enumerate(gene_names) if gene in tf_names]

    return expression_matrix[: tf_indices]


def to_links_df(regressor_type,
                trained_model,
                tf_names,
                target_gene_name):
    """
    :param regressor_type: one of ['RF', 'ET', 'GBM', 'XGB']. Case insensitive.
    :param trained_model: the trained model from which to extract the feature importances.
    :param tf_names: the list of names corresponding to the columns of the tf_matrix used to train the model.
    :param target_gene_name: the name of the target gene.
    :return: a Pandas DataFrame['TF', 'target', 'importance'] representing inferred regulatory links and their
             connection strength.
    """

    if __is_skl_regressor(regressor_type):
        importances = trained_model.feature_importances_

        links_df = pd.DataFrame({'TF': tf_names, 'importance': importances})
        links_df['target'] = target_gene_name

        return links_df[links_df.importance > 0].sort_values(by='importance', ascending=False)

    elif __is_xgboost_regressor(regressor_type):
        raise ValueError('XGB regressor not yet supported')  # TODO

    else:
        raise ValueError('Unsupported regressor type: ' + regressor_type)


def clean(tf_matrix,
          tf_names,
          target_gene_name):
    """
    :param tf_matrix: numpy array. The full transcription factor matrix.
    :param tf_names: the full list of transcriptor factor names, corresponding to the tf_matrix columns.
    :param target_gene_name: the target gene to remove from the th_matrix and tf_names.
    :return: a tuple of (matrix, names) equal to the specified ones minus the target_gene_name if the target happens
             to be one of the transcription factors. If not, the specified (tf_matrix, tf_names) is returned verbatim.
    """

    clean_tf_matrix = tf_matrix if target_gene_name not in tf_names else np.delete(tf_matrix, tf_names.index(target_gene_name), 1)
    clean_tf_names = [tf for tf in tf_names if tf != target_gene_name]

    assert clean_tf_matrix.shape[1] == len(clean_tf_names)  # sanity check

    return clean_tf_matrix, clean_tf_names


def infer_links(regressor_type,
                regressor_kwargs,
                tf_matrix,
                tf_names,
                target_gene_name,
                target_gene_expression,
                seed=THE_DEMON_SEED):
    """
    Top-level function. Ties together model training and feature importance extraction.

    :param regressor_type: one of ['RF', 'ET', 'GBM', 'XGB']. Case insensitive.
    :param regressor_kwargs: dict of key-value pairs that configures the regressor.
    :param tf_matrix: numpy matrix. The feature matrix X to use for the regression.
    :param tf_names: list of transcription factor names corresponding to the columns of the tf_matrix used to train the model.
    :param target_gene_name: the name of the target gene to infer the regulatory links for.
    :param target_gene_expression: the expression profile of the target gene. Numpy array.
    :param seed: (optional) random seed for the regressors.
    :return: a Pandas DataFrame['TF', 'target', 'importance'] representing inferred regulatory links and their
             connection strength.
    """

    (clean_tf_matrix, clean_tf_names) = clean(tf_matrix, tf_names, target_gene_name)

    model = train_model(regressor_type, regressor_kwargs, clean_tf_matrix, target_gene_expression, seed)

    return to_links_df(regressor_type, model, clean_tf_names, target_gene_name)


def __target_gene_indices(gene_names,
                          target_genes):
    """
    :param gene_names: list of gene names.
    :param target_genes: either int (the top n), 'all', or a collection (subset of gene_names).
    :return: the (column) indices of the target genes in the expression_matrix.
    """

    if target_genes.upper() == 'ALL':
        return list(range(len(gene_names)))

    elif isinstance(target_genes, int):
        top_n = target_genes  # rename for clarity
        assert top_n > 0
        assert top_n <= len(gene_names)

        return list(range(top_n))

    elif isinstance(target_genes, list):
        return [index for index, gene in enumerate(gene_names) if gene in target_genes]

    else:
        raise ValueError("Unable to interpret target_genes: " + target_genes)


def create_graph(expression_matrix,
                 gene_names,
                 tf_names,
                 regressor_type,
                 regressor_kwargs,
                 target_genes='all',
                 limit=100000,
                 seed=THE_DEMON_SEED):
    """
    Main API function. Create a Dask computation graph.

    :param expression_matrix: numpy matrix. Rows are observations and columns are genes.
    :param gene_names: list of gene names. Each entry corresponds to the expression_matrix column with same index.
    :param tf_names: list of transcription factor names. Should have a non-empty intersection with gene_names.
    :param regressor_type: one of ['RF', 'ET', 'GBM', 'XGB']. Case insensitive.
    :param regressor_kwargs: dict of key-value pairs that configures the regressor.
    :param target_genes: either int, 'all' or a collection that is a subset of gene_names.
    :param limit: int or None. Default 100k. The number of top regulatory links to return.
    :param seed: (optional) random seed for the regressors.
    :return: a dask computation graph instance.
    """

    tf_matrix = to_tf_matrix(expression_matrix, gene_names, tf_names)

    delayed_tf_matrix = delayed(tf_matrix)
    delayed_tf_names = delayed(tf_names)

    delayed_link_dfs = []  # collection of delayed link DataFrames

    for target_gene_index in __target_gene_indices(gene_names, target_genes):

        target_gene_name = gene_names[target_gene_index]
        target_gene_expression = expression_matrix[:, target_gene_index]

        delayed_link_df = delayed(infer_links)(
            regressor_type, regressor_kwargs,
            delayed_tf_matrix, delayed_tf_names,
            target_gene_name, target_gene_expression,
            seed)

        delayed_link_dfs.append(delayed_link_df)

    # provide the schema of the delayed DataFrames
    link_df_meta = make_meta({'TF': str, 'target': str, 'importance': float})

    # gather the regulatory link DataFrames into one distributed DataFrame
    all_links_df = from_delayed(delayed_link_dfs, meta=link_df_meta)

    # optionally limit the number of resulting regulatory links
    result = all_links_df.nlargest(limit, columns=['importance']) if isinstance(limit, int) else all_links_df

    return result['TF', 'target', 'importance']
