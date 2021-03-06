# -*- coding: utf-8 -*-
from __future__ import print_function
import argparse
import os
import sys
import time
import re
import tensorflow as tf
#import pandas as pd
import subprocess
import random
import numpy as np

from vocab_utils import Vocab
from SentenceMatchDataStream import SentenceMatchDataStream
from SentenceMatchModelGraph import SentenceMatchModelGraph
import namespace_utils

eps = 1e-8
FLAGS = None

def collect_vocabs(train_path, with_POS=False, with_NER=False):
    all_labels = set()
    all_words = set()
    all_POSs = None
    all_NERs = None
    if with_POS: all_POSs = set()
    if with_NER: all_NERs = set()
    infile = open(train_path, 'rt')
    for line in infile:
        line = line.decode('utf-8').strip()
        if line.startswith('-'): continue
        items = re.split("\t", line)
        label = items[2]
        sentence1 = re.split("\\s+",items[0].lower())
        sentence2 = re.split("\\s+",items[1].lower())
        all_labels.add(label)
        all_words.update(sentence1)
        all_words.update(sentence2)
        if with_POS: 
            all_POSs.update(re.split("\\s+",items[3]))
            all_POSs.update(re.split("\\s+",items[4]))
        if with_NER: 
            all_NERs.update(re.split("\\s+",items[5]))
            all_NERs.update(re.split("\\s+",items[6]))
    infile.close()

    all_chars = set()
    for word in all_words:
        for char in word:
            all_chars.add(char)
    return (all_words, all_chars, all_labels, all_POSs, all_NERs)

def evaluate(dataStream, valid_graph, sess, outpath=None,
             label_vocab=None, mode='trec',char_vocab=None, POS_vocab=None, NER_vocab=None):
    outpath = ''
    #if outpath is not None: outfile = open(outpath, 'wt')
    #subfile = ''
    #goldfile = ''
    #if FLAGS.is_answer_selection == True:
        #print ('open')
    #    outpath = '../trec_eval-8.0/'
    #    subfile = open(outpath + 'submission.txt', 'wt')
    #    goldfile = open(outpath + 'gold.txt', 'wt')
    #total_tags = 0.0
    #correct_tags = 0.0
    dataStream.reset()
    #last_trec = ""
    #id_trec = 0
    #doc_id_trec = 1
    #sub_list = []
    #has_true_label = set ()
    questions_count = 0.0
    MAP = 0.0
    MRR = 0.0
    for batch_index in xrange(dataStream.get_num_batch()):
        cur_dev_batch = dataStream.get_batch(batch_index)
        (label_batch, sent1_batch, sent2_batch, label_id_batch, word_idx_1_batch, word_idx_2_batch, 
                                 char_matrix_idx_1_batch, char_matrix_idx_2_batch, sent1_length_batch, sent2_length_batch, 
                                 sent1_char_length_batch, sent2_char_length_batch,
                                 POS_idx_1_batch, POS_idx_2_batch, NER_idx_1_batch, NER_idx_2_batch) = cur_dev_batch
        feed_dict = {
                    valid_graph.get_truth(): label_id_batch, 
                    valid_graph.get_question_lengths(): sent1_length_batch, 
                    valid_graph.get_passage_lengths(): sent2_length_batch, 
                    valid_graph.get_in_question_words(): word_idx_1_batch, 
                    valid_graph.get_in_passage_words(): word_idx_2_batch, 
#                     valid_graph.get_question_char_lengths(): sent1_char_length_batch, 
#                     valid_graph.get_passage_char_lengths(): sent2_char_length_batch, 
#                     valid_graph.get_in_question_chars(): char_matrix_idx_1_batch, 
#                     valid_graph.get_in_passage_chars(): char_matrix_idx_2_batch, 
                }

        if char_vocab is not None:
            feed_dict[valid_graph.get_question_char_lengths()] = sent1_char_length_batch
            feed_dict[valid_graph.get_passage_char_lengths()] = sent2_char_length_batch
            feed_dict[valid_graph.get_in_question_chars()] = char_matrix_idx_1_batch
            feed_dict[valid_graph.get_in_passage_chars()] = char_matrix_idx_2_batch

        if POS_vocab is not None:
            feed_dict[valid_graph.get_in_question_poss()] = POS_idx_1_batch
            feed_dict[valid_graph.get_in_passage_poss()] = POS_idx_2_batch

        if NER_vocab is not None:
            feed_dict[valid_graph.get_in_question_ners()] = NER_idx_1_batch
            feed_dict[valid_graph.get_in_passage_ners()] = NER_idx_2_batch

        if FLAGS.is_answer_selection == True:
            feed_dict[valid_graph.get_question_count()] = dataStream.question_count(batch_index)
            feed_dict[valid_graph.get_answer_count()] = dataStream.answer_count(batch_index)

        #total_tags += len(label_batch)
        #correct_tags += sess.run(valid_graph.get_eval_correct(), feed_dict=feed_dict)
        if outpath is not None:
            #if mode =='prediction':
            #    predictions = sess.run(valid_graph.get_predictions(), feed_dict=feed_dict)
            #    for i in xrange(len(label_batch)):
            #        outline = label_batch[i] + "\t" + label_vocab.getWord(predictions[i]) + "\t" + sent1_batch[i] + "\t" + sent2_batch[i] + "\n"
            #        outfile.write(outline.encode('utf-8'))

            if FLAGS.is_answer_selection == True:
                probs = sess.run(valid_graph.get_prob(), feed_dict=feed_dict)
                (my_map, my_mrr) = MAP_MRR(probs, label_id_batch,dataStream.question_count(batch_index),
                        dataStream.answer_count(batch_index))
                MAP += my_map
                MRR += my_mrr
                questions_count += dataStream.question_count(batch_index)
                # for i in xrange(len(label_batch)):
                #     if sent1_batch[i] != last_trec:
                #         last_trec = sent1_batch[i]
                #         id_trec += 1
                #     if (FLAGS.prediction_mode == 'point_wise'):
                #         pbi = ouput_prob1(probs[i], label_vocab, '1')
                #     else:
                #         pbi = probs[i]
                #     if (label_batch[i] == '1'):
                #         has_true_label.add(id_trec)
                #     sub_list.append((id_trec, doc_id_trec, pbi, label_batch[i]))
                #     doc_id_trec +=1
            #else:
                #probs = sess.run(valid_graph.get_prob(), feed_dict=feed_dict)
                #for i in xrange(len(label_batch)):
                #    outfile.write(label_batch[i] + "\t" + output_probs(probs[i], label_vocab) + "\n")

    #print ('start')

    #if FLAGS.is_answer_selection == False:
    #    if outpath is not None: outfile.close()

    if FLAGS.is_answer_selection == True:
        my_map = MAP/questions_count
        my_mrr = MRR/questions_count
        # print (final_map, final_mrr)
        # for i in xrange(len (sub_list)):
        #     id_trec, doc_id_trec, prob1, label_gold = sub_list[i]
        #     if id_trec in has_true_label:
        #         subfile.write(str(id_trec) + " 0 " + str(doc_id_trec)
        #                       + " 0 " + str(prob1) + ' nnet\n')
        #         goldfile.write(str(id_trec) + " 0 " + str(doc_id_trec)
        #                        + " " + label_gold + '\n')
        # subfile.close()
        # goldfile.close()
        #print ('hi')
        # p = subprocess.check_output("/bin/sh ../run_eval.sh '{}'".format(outpath),
        #                 shell=True)
        #print (p)
        # p = p.split()
        #my_map = float(p[2])
        #my_mrr = float(p[5])

        #print("map '{}' , mrr '{}'".format(my_map, my_mrr))

    #    print ('end')
        return (my_map, my_mrr)

    #accuracy = correct_tags / total_tags * 100
    #return accuracy


def MAP_MRR(logit, gold, question_count, answer_count):
    c_1_j = 0.0 #map
    c_2_j = 0.0 #mrr
    for i in xrange(question_count):
        prob = logit[i * answer_count:(i + 1) *answer_count]
        label = gold[i * answer_count:(i + 1) *answer_count]
        rank_index = np.argsort(prob).tolist()
        rank_index = list(reversed(rank_index))
        score = 0.0
        count = 0.0
        for i in xrange(1, len(prob) + 1):
            if label[rank_index[i - 1]] > eps:
                count += 1
                score += count / i
        for i in range(1, len(prob) + 1):
            if label[rank_index[i - 1]] > eps:
                c_2_j += 1 / float(i)
                break
        c_1_j += score / count
    return (c_1_j, c_2_j)

def ouput_prob1(probs, label_vocab, lable_true):
    out_string = ""
    for i in xrange(probs.size):
        if label_vocab.getWord(i) == lable_true:
            return probs[i]

def output_probs(probs, label_vocab):
    out_string = ""
    for i in xrange(probs.size):
        out_string += " {}:{}".format(label_vocab.getWord(i), probs[i])
    return out_string.strip()


def Generate_random_initialization():
    if FLAGS.is_server == True:
        configuration = [1, 2, 3, 4, 5]
        #1 : attention lstm agg
        #2 : cnn stack and highway
        #3 : context self attention
        #4 : aggregation self attention
        cnf = random.choice(configuration)
        FLAGS.cnf = cnf
        type1 = ['mul']
        type2 = ['mul', 'w_sub_mul',None]
        type3 = [None]
        FLAGS.type1 = random.choice(type1)
        FLAGS.type2 = random.choice(type2)
        FLAGS.type3 = random.choice(type3)
        context_layer_num = [1]
        aggregation_layer_num = [1]
        FLAGS.aggregation_layer_num = random.choice(aggregation_layer_num)
        FLAGS.context_layer_num = random.choice(context_layer_num)
        #if cnf == 1  or cnf == 4:
        #    is_aggregation_lstm = [True]
        #elif cnf == 2:
        #    is_aggregation_lstm =  [False]
        #else: #3
        is_aggregation_lstm = [True, False]
        FLAGS.is_aggregation_lstm = random.choice(is_aggregation_lstm)
        max_window_size = [1] #[x for x in range (1, 4, 1)]
        FLAGS.max_window_size = random.choice(max_window_size)

        att_cnt = 0
        if FLAGS.type1 != None:
            att_cnt += 1
        if FLAGS.type2 != None:
            att_cnt += 1
        if FLAGS.type3 != None:
            att_cnt += 1


        #context_lstm_dim:
        if FLAGS.context_layer_num == 2:
            context_lstm_dim = [50] #[x for x in range(50, 110, 10)]
        else:
            context_lstm_dim = [50]#[x for x in range(50, 160, 10)]

        if FLAGS.is_aggregation_lstm == True:
            if FLAGS.aggregation_layer_num == 2:
                aggregation_lstm_dim = [50]#[x for x in range (50, 110, 10)]
            else:
                aggregation_lstm_dim = [50]#[x for x in range (50, 160, 10)]
        else: # CNN
            if FLAGS.max_window_size == 1:
                aggregation_lstm_dim = [100]#[x for x in range (50, 801, 10)]
            elif FLAGS.max_window_size == 2:
                aggregation_lstm_dim = [100]#[x for x in range (50, 510, 10)]
            elif FLAGS.max_window_size == 3:
                aggregation_lstm_dim = [50]#[x for x in range (50, 410, 10)]
            elif FLAGS.max_window_size == 4:
                aggregation_lstm_dim = [x for x in range (50, 210, 10)]
            else: #5
                aggregation_lstm_dim = [x for x in range (50, 110, 10)]


        MP_dim = [20,50,100]#[x for x in range (20, 610, 10)]
        #batch_size = [x for x in range (30, 80, 10)] we can not determine batch_size here
        learning_rate = [0.002]#[0.001, 0.002, 0.003, 0.004]
        dropout_rate = [0.04]#[x/100.0 for x in xrange (2, 30, 2)]
        char_lstm_dim = [80] #[x for x in range(40, 110, 10)]
        char_emb_dim = [40] #[x for x in range (20, 110, 10)]
        wo_char = [True]
        wo_lstm_drop_out = [True]
        if cnf == 4:
            wo_agg_self_att = [False, True]
        else:
            wo_agg_self_att = [True]
        is_shared_attention = [False, True]
        modify_loss = [0.1]#[x/10.0 for x in range (0, 5, 1)]
        prediction_mode = ['list_wise']
        #if cnf == 2:
        unstack_cnn = [False, True]
        #else:
        #    unstack_cnn = [False, True]
        with_highway = [False]
        if FLAGS.is_aggregation_lstm == False:
            with_match_highway = [True, False]
        else:
            with_match_highway = [False]
        with_aggregation_highway = [False]
        highway_layer_num = [1]
        is_aggregation_siamese = [False, True]

        #if cnf == 1:
        attention_type = ['bilinear', 'linear', 'linear_p_bias', 'dot_product']
        #else:
        #attention_type = ['bilinear']
        if cnf == 3:
            with_context_self_attention = [False, True]
        else:
            with_context_self_attention = [False]
        FLAGS.with_context_self_attention = random.choice(with_context_self_attention)
        #FLAGS.batch_size = random.choice(batch_size)
        FLAGS.unstack_cnn = random.choice(unstack_cnn)
        FLAGS.attention_type = random.choice(attention_type)
        FLAGS.learning_rate = random.choice(learning_rate)
        FLAGS.dropout_rate = random.choice(dropout_rate)
        FLAGS.char_lstm_dim = random.choice(char_lstm_dim)
        FLAGS.context_lstm_dim = random.choice(context_lstm_dim)
        FLAGS.aggregation_lstm_dim = random.choice(aggregation_lstm_dim)
        FLAGS.MP_dim = random.choice(MP_dim)
        FLAGS.char_emb_dim = random.choice(char_emb_dim)
        FLAGS.with_aggregation_highway = random.choice(with_aggregation_highway)
        FLAGS.wo_char = random.choice(wo_char)
        FLAGS.wo_lstm_drop_out = random.choice(wo_lstm_drop_out)
        FLAGS.wo_agg_self_att = random.choice(wo_agg_self_att)
        FLAGS.is_shared_attention = random.choice(is_shared_attention)
        FLAGS.modify_loss = random.choice(modify_loss)
        FLAGS.prediction_mode = random.choice(prediction_mode)
        FLAGS.with_match_highway = random.choice(with_match_highway)
        FLAGS.with_highway = random.choice(with_highway)
        FLAGS.highway_layer_num = random.choice(highway_layer_num)
        FLAGS.is_aggregation_siamese = random.choice(is_aggregation_siamese)

        #
        # FLAGS.MP_dim = FLAGS.MP_dim // (att_cnt*FLAGS.context_layer_num)
        # FLAGS.MP_dim = (FLAGS.MP_dim+10) - FLAGS.MP_dim % 10
        #
        # if (FLAGS.type1 == 'mul' or FLAGS.type2 == 'mul' or FLAGS.type3 == 'mul'):
        #     clstm = FLAGS.context_lstm_dim
        #     mp = FLAGS.MP_dim
        #     while (clstm*2) % mp != 0:
        #         mp -= 10
        #     FLAGS.MP_dim = mp



def main(_):


    #for x in range (100):
    #    Generate_random_initialization()
    #    print (FLAGS.is_aggregation_lstm, FLAGS.context_lstm_dim, FLAGS.context_layer_num, FLAGS. aggregation_lstm_dim, FLAGS.aggregation_layer_num, FLAGS.max_window_size, FLAGS.MP_dim)

    print('Configurations:')
    #print(FLAGS)


    train_path = FLAGS.train_path
    dev_path = FLAGS.dev_path
    test_path = FLAGS.test_path
    word_vec_path = FLAGS.word_vec_path
    log_dir = FLAGS.model_dir
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    path_prefix = log_dir + "/SentenceMatch.{}".format(FLAGS.suffix)

    namespace_utils.save_namespace(FLAGS, path_prefix + ".config.json")

    # build vocabs
    word_vocab = Vocab(word_vec_path, fileformat='txt3')
    best_path = path_prefix + '.best.model'
    char_path = path_prefix + ".char_vocab"
    label_path = path_prefix + ".label_vocab"
    POS_path = path_prefix + ".POS_vocab"
    NER_path = path_prefix + ".NER_vocab"
    has_pre_trained_model = False
    POS_vocab = None
    NER_vocab = None
    if os.path.exists(best_path):
        has_pre_trained_model = True
        label_vocab = Vocab(label_path, fileformat='txt2')
        char_vocab = Vocab(char_path, fileformat='txt2')
        if FLAGS.with_POS: POS_vocab = Vocab(POS_path, fileformat='txt2')
        if FLAGS.with_NER: NER_vocab = Vocab(NER_path, fileformat='txt2')
    else:
        print('Collect words, chars and labels ...')
        (all_words, all_chars, all_labels, all_POSs, all_NERs) = collect_vocabs(train_path, with_POS=FLAGS.with_POS, with_NER=FLAGS.with_NER)
        print('Number of words: {}'.format(len(all_words)))
        print('Number of labels: {}'.format(len(all_labels)))
        label_vocab = Vocab(fileformat='voc', voc=all_labels,dim=2)
        label_vocab.dump_to_txt2(label_path)

        print('Number of chars: {}'.format(len(all_chars)))
        char_vocab = Vocab(fileformat='voc', voc=all_chars,dim=FLAGS.char_emb_dim)
        char_vocab.dump_to_txt2(char_path)
        
        if FLAGS.with_POS:
            print('Number of POSs: {}'.format(len(all_POSs)))
            POS_vocab = Vocab(fileformat='voc', voc=all_POSs,dim=FLAGS.POS_dim)
            POS_vocab.dump_to_txt2(POS_path)
        if FLAGS.with_NER:
            print('Number of NERs: {}'.format(len(all_NERs)))
            NER_vocab = Vocab(fileformat='voc', voc=all_NERs,dim=FLAGS.NER_dim)
            NER_vocab.dump_to_txt2(NER_path)
            

    print('word_vocab shape is {}'.format(word_vocab.word_vecs.shape))
    print('tag_vocab shape is {}'.format(label_vocab.word_vecs.shape))
    num_classes = label_vocab.size()

    print('Build SentenceMatchDataStream ... ')
    trainDataStream = SentenceMatchDataStream(train_path, word_vocab=word_vocab, char_vocab=char_vocab, 
                                              POS_vocab=POS_vocab, NER_vocab=NER_vocab, label_vocab=label_vocab, 
                                              batch_size=FLAGS.batch_size, isShuffle=True, isLoop=True, isSort=True, 
                                              max_char_per_word=FLAGS.max_char_per_word, max_sent_length=FLAGS.max_sent_length,
                                              is_as=FLAGS.is_answer_selection)
                                    
    devDataStream = SentenceMatchDataStream(dev_path, word_vocab=word_vocab, char_vocab=char_vocab,
                                              POS_vocab=POS_vocab, NER_vocab=NER_vocab, label_vocab=label_vocab, 
                                              batch_size=FLAGS.batch_size, isShuffle=False, isLoop=True, isSort=True,
                                              max_char_per_word=FLAGS.max_char_per_word, max_sent_length=FLAGS.max_sent_length,
                                              is_as=FLAGS.is_answer_selection)

    testDataStream = SentenceMatchDataStream(test_path, word_vocab=word_vocab, char_vocab=char_vocab, 
                                              POS_vocab=POS_vocab, NER_vocab=NER_vocab, label_vocab=label_vocab, 
                                              batch_size=FLAGS.batch_size, isShuffle=False, isLoop=True, isSort=True,
                                              max_char_per_word=FLAGS.max_char_per_word, max_sent_length=FLAGS.max_sent_length,
                                              is_as=FLAGS.is_answer_selection)

    print('Number of instances in trainDataStream: {}'.format(trainDataStream.get_num_instance()))
    print('Number of instances in devDataStream: {}'.format(devDataStream.get_num_instance()))
    print('Number of instances in testDataStream: {}'.format(testDataStream.get_num_instance()))
    print('Number of batches in trainDataStream: {}'.format(trainDataStream.get_num_batch()))
    print('Number of batches in devDataStream: {}'.format(devDataStream.get_num_batch()))
    print('Number of batches in testDataStream: {}'.format(testDataStream.get_num_batch()))
    
    sys.stdout.flush()
    if FLAGS.wo_char: char_vocab = None
    output_res_index = 1
    while True:
        Generate_random_initialization()
        st_cuda = ''
        if FLAGS.is_server == True:
            st_cuda = str(os.environ['CUDA_VISIBLE_DEVICES']) + '.'
        output_res_file = open('../result/' + st_cuda + str(output_res_index), 'wt')
        output_res_index += 1
        output_res_file.write(str(FLAGS) + '\n\n')
        stt = str (FLAGS)
        best_accuracy = 0.0
        init_scale = 0.01
        with tf.Graph().as_default():
            initializer = tf.random_uniform_initializer(-init_scale, init_scale)
    #         with tf.name_scope("Train"):
            with tf.variable_scope("Model", reuse=None, initializer=initializer):
                train_graph = SentenceMatchModelGraph(num_classes, word_vocab=word_vocab, char_vocab=char_vocab, POS_vocab=POS_vocab, NER_vocab=NER_vocab,
                                                      dropout_rate=FLAGS.dropout_rate, learning_rate=FLAGS.learning_rate, optimize_type=FLAGS.optimize_type,
                                                      lambda_l2=FLAGS.lambda_l2, char_lstm_dim=FLAGS.char_lstm_dim, context_lstm_dim=FLAGS.context_lstm_dim,
                                                      aggregation_lstm_dim=FLAGS.aggregation_lstm_dim, is_training=True, MP_dim=FLAGS.MP_dim,
                                                      context_layer_num=FLAGS.context_layer_num, aggregation_layer_num=FLAGS.aggregation_layer_num,
                                                      fix_word_vec=FLAGS.fix_word_vec, with_filter_layer=FLAGS.with_filter_layer, with_input_highway=FLAGS.with_highway,
                                                      word_level_MP_dim=FLAGS.word_level_MP_dim,
                                                      with_match_highway=FLAGS.with_match_highway, with_aggregation_highway=FLAGS.with_aggregation_highway,
                                                      highway_layer_num=FLAGS.highway_layer_num, with_lex_decomposition=FLAGS.with_lex_decomposition,
                                                      lex_decompsition_dim=FLAGS.lex_decompsition_dim,
                                                      with_left_match=(not FLAGS.wo_left_match), with_right_match=(not FLAGS.wo_right_match),
                                                      with_full_match=(not FLAGS.wo_full_match), with_maxpool_match=(not FLAGS.wo_maxpool_match),
                                                      with_attentive_match=(not FLAGS.wo_attentive_match), with_max_attentive_match=(not FLAGS.wo_max_attentive_match),
                                                      with_bilinear_att=(FLAGS.attention_type)
                                                      , type1=FLAGS.type1, type2 = FLAGS.type2, type3=FLAGS.type3,
                                                      with_aggregation_attention=not FLAGS.wo_agg_self_att,
                                                      is_answer_selection= FLAGS.is_answer_selection,
                                                      is_shared_attention=FLAGS.is_shared_attention,
                                                      modify_loss=FLAGS.modify_loss, is_aggregation_lstm=FLAGS.is_aggregation_lstm
                                                      , max_window_size=FLAGS.max_window_size
                                                      , prediction_mode=FLAGS.prediction_mode,
                                                      context_lstm_dropout=not FLAGS.wo_lstm_drop_out,
                                                      is_aggregation_siamese=FLAGS.is_aggregation_siamese
                                                      , unstack_cnn=FLAGS.unstack_cnn,with_context_self_attention=FLAGS.with_context_self_attention)
                tf.summary.scalar("Training Loss", train_graph.get_loss()) # Add a scalar summary for the snapshot loss.

    #         with tf.name_scope("Valid"):
            with tf.variable_scope("Model", reuse=True, initializer=initializer):
                valid_graph = SentenceMatchModelGraph(num_classes, word_vocab=word_vocab, char_vocab=char_vocab, POS_vocab=POS_vocab, NER_vocab=NER_vocab,
                                                      dropout_rate=FLAGS.dropout_rate, learning_rate=FLAGS.learning_rate, optimize_type=FLAGS.optimize_type,
                                                      lambda_l2=FLAGS.lambda_l2, char_lstm_dim=FLAGS.char_lstm_dim, context_lstm_dim=FLAGS.context_lstm_dim,
                                                      aggregation_lstm_dim=FLAGS.aggregation_lstm_dim, is_training=False, MP_dim=FLAGS.MP_dim,
                                                      context_layer_num=FLAGS.context_layer_num, aggregation_layer_num=FLAGS.aggregation_layer_num,
                                                      fix_word_vec=FLAGS.fix_word_vec, with_filter_layer=FLAGS.with_filter_layer, with_input_highway=FLAGS.with_highway,
                                                      word_level_MP_dim=FLAGS.word_level_MP_dim,
                                                      with_match_highway=FLAGS.with_match_highway, with_aggregation_highway=FLAGS.with_aggregation_highway,
                                                      highway_layer_num=FLAGS.highway_layer_num, with_lex_decomposition=FLAGS.with_lex_decomposition,
                                                      lex_decompsition_dim=FLAGS.lex_decompsition_dim,
                                                      with_left_match=(not FLAGS.wo_left_match), with_right_match=(not FLAGS.wo_right_match),
                                                      with_full_match=(not FLAGS.wo_full_match), with_maxpool_match=(not FLAGS.wo_maxpool_match),
                                                      with_attentive_match=(not FLAGS.wo_attentive_match), with_max_attentive_match=(not FLAGS.wo_max_attentive_match),
                                                      with_bilinear_att=(FLAGS.attention_type)
                                                      , type1=FLAGS.type1, type2 = FLAGS.type2, type3=FLAGS.type3,
                                                      with_aggregation_attention=not FLAGS.wo_agg_self_att,
                                                      is_answer_selection= FLAGS.is_answer_selection,
                                                      is_shared_attention=FLAGS.is_shared_attention,
                                                      modify_loss=FLAGS.modify_loss, is_aggregation_lstm=FLAGS.is_aggregation_lstm,
                                                      max_window_size=FLAGS.max_window_size
                                                      , prediction_mode=FLAGS.prediction_mode,
                                                      context_lstm_dropout=not FLAGS.wo_lstm_drop_out,
                                                      is_aggregation_siamese=FLAGS.is_aggregation_siamese
                                                      , unstack_cnn=FLAGS.unstack_cnn,with_context_self_attention=FLAGS.with_context_self_attention)


            initializer = tf.global_variables_initializer()
            vars_ = {}
            #for var in tf.all_variables():
            for var in tf.global_variables():
                if "word_embedding" in var.name: continue
    #             if not var.name.startswith("Model"): continue
                vars_[var.name.split(":")[0]] = var
            saver = tf.train.Saver(vars_)

            with tf.Session() as sess:
                sess.run(initializer)
                if has_pre_trained_model:
                    print("Restoring model from " + best_path)
                    saver.restore(sess, best_path)
                    print("DONE!")

                print('Start the training loop.')
                train_size = trainDataStream.get_num_batch()
                max_steps = train_size * FLAGS.max_epochs
                total_loss = 0.0
                start_time = time.time()

                for step in xrange(max_steps):
                    # read data
                    cur_batch, batch_index = trainDataStream.nextBatch()
                    (label_batch, sent1_batch, sent2_batch, label_id_batch, word_idx_1_batch, word_idx_2_batch,
                                         char_matrix_idx_1_batch, char_matrix_idx_2_batch, sent1_length_batch, sent2_length_batch,
                                         sent1_char_length_batch, sent2_char_length_batch,
                                         POS_idx_1_batch, POS_idx_2_batch, NER_idx_1_batch, NER_idx_2_batch) = cur_batch
                    feed_dict = {
                                 train_graph.get_truth(): label_id_batch,
                                 train_graph.get_question_lengths(): sent1_length_batch,
                                 train_graph.get_passage_lengths(): sent2_length_batch,
                                 train_graph.get_in_question_words(): word_idx_1_batch,
                                 train_graph.get_in_passage_words(): word_idx_2_batch,
        #                          train_graph.get_question_char_lengths(): sent1_char_length_batch,
        #                          train_graph.get_passage_char_lengths(): sent2_char_length_batch,
        #                          train_graph.get_in_question_chars(): char_matrix_idx_1_batch,
        #                          train_graph.get_in_passage_chars(): char_matrix_idx_2_batch,
                                 }
                    if char_vocab is not None:
                        feed_dict[train_graph.get_question_char_lengths()] = sent1_char_length_batch
                        feed_dict[train_graph.get_passage_char_lengths()] = sent2_char_length_batch
                        feed_dict[train_graph.get_in_question_chars()] = char_matrix_idx_1_batch
                        feed_dict[train_graph.get_in_passage_chars()] = char_matrix_idx_2_batch

                    if POS_vocab is not None:
                        feed_dict[train_graph.get_in_question_poss()] = POS_idx_1_batch
                        feed_dict[train_graph.get_in_passage_poss()] = POS_idx_2_batch

                    if NER_vocab is not None:
                        feed_dict[train_graph.get_in_question_ners()] = NER_idx_1_batch
                        feed_dict[train_graph.get_in_passage_ners()] = NER_idx_2_batch

                    if FLAGS.is_answer_selection == True:
                        feed_dict[train_graph.get_question_count()] = trainDataStream.question_count(batch_index)
                        feed_dict[train_graph.get_answer_count()] = trainDataStream.answer_count(batch_index)

                    _, loss_value = sess.run([train_graph.get_train_op(), train_graph.get_loss()], feed_dict=feed_dict)
                    total_loss += loss_value
                    if FLAGS.is_answer_selection == True and FLAGS.is_server == False:
                        print ("q: {} a: {} loss_value: {}".format(trainDataStream.question_count(batch_index)
                                                   ,trainDataStream.answer_count(batch_index), loss_value))

                    if step % 100==0:
                        print('{} '.format(step), end="")
                        sys.stdout.flush()

                    # Save a checkpoint and evaluate the model periodically.
                    if (step + 1) % trainDataStream.get_num_batch() == 0 or (step + 1) == max_steps:
                        #print(total_loss)
                        # Print status to stdout.
                        duration = time.time() - start_time
                        start_time = time.time()
                        output_res_file.write('Step %d: loss = %.2f (%.3f sec)\n' % (step, total_loss, duration))
                        total_loss = 0.0


                        #Evaluate against the validation set.
                        output_res_file.write('valid- ')
                        my_map, my_mrr = evaluate(devDataStream, valid_graph, sess,char_vocab=char_vocab,
                                            POS_vocab=POS_vocab, NER_vocab=NER_vocab, label_vocab=label_vocab)
                        output_res_file.write("map: '{}', mrr: '{}'\n".format(my_map, my_mrr))
                        #print ("dev map: {}".format(my_map))
                        #print("Current accuracy is %.2f" % accuracy)

                        #accuracy = my_map
                        #if accuracy>best_accuracy:
                        #    best_accuracy = accuracy
                        #    saver.save(sess, best_path)

                        # Evaluate against the test set.
                        output_res_file.write ('test- ')
                        my_map, my_mrr = evaluate(testDataStream, valid_graph, sess, char_vocab=char_vocab,
                                 POS_vocab=POS_vocab, NER_vocab=NER_vocab, label_vocab=label_vocab)
                        output_res_file.write("map: '{}', mrr: '{}\n\n".format(my_map, my_mrr))
                        if FLAGS.is_server == False:
                            print ("test map: {}".format(my_map))

                        #Evaluate against the train set only for final epoch.
                        if (step + 1) == max_steps:
                            output_res_file.write ('train- ')
                            my_map, my_mrr = evaluate(trainDataStream, valid_graph, sess, char_vocab=char_vocab,
                                POS_vocab=POS_vocab, NER_vocab=NER_vocab, label_vocab=label_vocab)
                            output_res_file.write("map: '{}', mrr: '{}'\n".format(my_map, my_mrr))

        # print("Best accuracy on dev set is %.2f" % best_accuracy)
        # # decoding
        # print('Decoding on the test set:')
        # init_scale = 0.01
        # with tf.Graph().as_default():
        #     initializer = tf.random_uniform_initializer(-init_scale, init_scale)
        #     with tf.variable_scope("Model", reuse=False, initializer=initializer):
        #         valid_graph = SentenceMatchModelGraph(num_classes, word_vocab=word_vocab, char_vocab=char_vocab, POS_vocab=POS_vocab, NER_vocab=NER_vocab,
        #              dropout_rate=FLAGS.dropout_rate, learning_rate=FLAGS.learning_rate, optimize_type=FLAGS.optimize_type,
        #              lambda_l2=FLAGS.lambda_l2, char_lstm_dim=FLAGS.char_lstm_dim, context_lstm_dim=FLAGS.context_lstm_dim,
        #              aggregation_lstm_dim=FLAGS.aggregation_lstm_dim, is_training=False, MP_dim=FLAGS.MP_dim,
        #              context_layer_num=FLAGS.context_layer_num, aggregation_layer_num=FLAGS.aggregation_layer_num,
        #              fix_word_vec=FLAGS.fix_word_vec,with_filter_layer=FLAGS.with_filter_layer, with_highway=FLAGS.with_highway,
        #              word_level_MP_dim=FLAGS.word_level_MP_dim,
        #              with_match_highway=FLAGS.with_match_highway, with_aggregation_highway=FLAGS.with_aggregation_highway,
        #              highway_layer_num=FLAGS.highway_layer_num, with_lex_decomposition=FLAGS.with_lex_decomposition,
        #              lex_decompsition_dim=FLAGS.lex_decompsition_dim,
        #              with_left_match=(not FLAGS.wo_left_match), with_right_match=(not FLAGS.wo_right_match),
        #              with_full_match=(not FLAGS.wo_full_match), with_maxpool_match=(not FLAGS.wo_maxpool_match),
        #              with_attentive_match=(not FLAGS.wo_attentive_match), with_max_attentive_match=(not FLAGS.wo_max_attentive_match),
        #                                               with_bilinear_att=(not FLAGS.wo_bilinear_att)
        #                                               , type1=FLAGS.type1, type2 = FLAGS.type2, type3=FLAGS.type3,
        #                                               with_aggregation_attention=not FLAGS.wo_agg_self_att,
        #                                               is_answer_selection= FLAGS.is_answer_selection,
        #                                               is_shared_attention=FLAGS.is_shared_attention,
        #                                               modify_loss=FLAGS.modify_loss,is_aggregation_lstm=FLAGS.is_aggregation_lstm,
        #                                               max_window_size=FLAGS.max_window_size,
        #                                               prediction_mode=FLAGS.prediction_mode,
        #                                               context_lstm_dropout=not FLAGS.wo_lstm_drop_out,
        #                                              is_aggregation_siamese=FLAGS.is_aggregation_siamese)
        #
        #     vars_ = {}
        #     for var in tf.global_variables():
        #         if "word_embedding" in var.name: continue
        #         if not var.name.startswith("Model"): continue
        #         vars_[var.name.split(":")[0]] = var
        #     saver = tf.train.Saver(vars_)
        #
        #     sess = tf.Session()
        #     sess.run(tf.global_variables_initializer())
        #     step = 0
        #     saver.restore(sess, best_path)
        #
        #     accuracy, mrr = evaluate(testDataStream, valid_graph, sess,char_vocab=char_vocab,POS_vocab=POS_vocab, NER_vocab=NER_vocab, label_vocab=label_vocab
        #                         , mode='trec')
        #     output_res_file.write("map for test set is %.2f\n" % accuracy)
        output_res_file.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--word_vec_path', type=str, default='../data/glove/glove.6B.50d.txt', help='Path the to pre-trained word vector model.')
    #parser.add_argument('--word_vec_path', type=str, default='../data/glove/glove.840B.300d.txt', help='Path the to pre-trained word vector model.')
    parser.add_argument('--is_server',default=True, help='loop: ranom initalizaion of parameters -> run ?')
    parser.add_argument('--max_epochs', type=int, default=13, help='Maximum epochs for training.')
    parser.add_argument('--attention_type', default='linear_p_bias', help='[bilinear, linear, linear_p_bias, dot_product]', action='store_true')


    parser.add_argument('--batch_size', type=int, default=40, help='Number of instances in each batch.')
    parser.add_argument('--is_answer_selection',default=True, help='is answer selection or other sentence matching tasks?')
    parser.add_argument('--optimize_type', type=str, default='adam', help='Optimizer type.')
    parser.add_argument('--prediction_mode', default='list_wise', help = 'point_wise, list_wise, hinge_wise .'
                                                                          'point wise is only used for non answer selection tasks')

    parser.add_argument('--train_path', type=str,default = '../data/wikiqa/WikiQACorpus/WikiQA-train.txt', help='Path to the train set.')
    parser.add_argument('--dev_path', type=str, default = '../data/wikiqa/WikiQACorpus/WikiQA-dev.txt', help='Path to the dev set.')
    parser.add_argument('--test_path', type=str, default = '../data/wikiqa/WikiQACorpus/WikiQA-test.txt',help='Path to the test set.')
    parser.add_argument('--model_dir', type=str,default = '../models',help='Directory to save model files.')

    parser.add_argument('--learning_rate', type=float, default=0.001, help='Learning rate.')
    parser.add_argument('--lambda_l2', type=float, default=0.0, help='The coefficient of L2 regularizer.')
    parser.add_argument('--dropout_rate', type=float, default=0.04, help='Dropout ratio.')
    parser.add_argument('--char_emb_dim', type=int, default=20, help='Number of dimension for character embeddings.')
    parser.add_argument('--char_lstm_dim', type=int, default=20, help='Number of dimension for character-composed embeddings.')
    parser.add_argument('--context_lstm_dim', type=int, default=50, help='Number of dimension for context representation layer.')
    parser.add_argument('--aggregation_lstm_dim', type=int, default=50, help='Number of dimension for aggregation layer.')
    parser.add_argument('--MP_dim', type=int, default=20, help='Number of perspectives for matching vectors.')
    parser.add_argument('--max_char_per_word', type=int, default=10, help='Maximum number of characters for each word.')
    parser.add_argument('--max_sent_length', type=int, default=100, help='Maximum number of words within each sentence.')
    parser.add_argument('--aggregation_layer_num', type=int, default=1, help='Number of LSTM layers for aggregation layer.')
    parser.add_argument('--context_layer_num', type=int, default=1, help='Number of LSTM layers for context representation layer.')
    parser.add_argument('--highway_layer_num', type=int, default=0, help='Number of highway layers.')
    parser.add_argument('--suffix', type=str, default='normal', required=False, help='Suffix of the model name.')
    parser.add_argument('--with_highway', default=False, help='Utilize highway layers.', action='store_true')
    parser.add_argument('--with_match_highway', default=False, help='Utilize highway layers for matching layer.', action='store_true')
    parser.add_argument('--with_aggregation_highway', default=False, help='Utilize highway layers for aggregation layer.', action='store_true')
    parser.add_argument('--wo_char', default=True, help='Without character-composed embeddings.', action='store_true')
    parser.add_argument('--type1', default='w_sub_mul', help='similrty function 1', action='store_true')
    parser.add_argument('--type2', default= 'w_sub_mul' , help='similrty function 2', action='store_true')
    parser.add_argument('--type3', default= 'mul' , help='similrty function 3', action='store_true')
    parser.add_argument('--wo_lstm_drop_out', default=  True , help='with out context lstm drop out', action='store_true')
    parser.add_argument('--wo_agg_self_att', default= True , help='with out aggregation lstm self attention', action='store_true')
    parser.add_argument('--is_shared_attention', default= False , help='are matching attention values shared or not', action='store_true')
    parser.add_argument('--modify_loss', type=float, default=0.1, help='a parameter used for loss.')
    parser.add_argument('--is_aggregation_lstm', default=False, help = 'is aggregation lstm or aggregation cnn' )
    parser.add_argument('--max_window_size', type=int, default=2, help = '[1..max_window_size] convolution')
    parser.add_argument('--is_aggregation_siamese', default=False, help = 'are aggregation wieghts on both sides shared or not' )
    parser.add_argument('--unstack_cnn', default=False, help = 'are aggregation wieghts on both sides shared or not' )
    parser.add_argument('--with_context_self_attention', default=True, help = 'are aggregation wieghts on both sides shared or not' )



    #these parameters arent used anymore:
    parser.add_argument('--with_filter_layer', default=False, help='Utilize filter layer.', action='store_true')
    parser.add_argument('--word_level_MP_dim', type=int, default=-1, help='Number of perspectives for word-level matching.')
    parser.add_argument('--with_lex_decomposition', default=False, help='Utilize lexical decomposition features.',
                        action='store_true')
    parser.add_argument('--lex_decompsition_dim', type=int, default=-1,
                        help='Number of dimension for lexical decomposition features.')
    parser.add_argument('--with_POS', default=False, help='Utilize POS information.', action='store_true')
    parser.add_argument('--with_NER', default=False, help='Utilize NER information.', action='store_true')
    parser.add_argument('--POS_dim', type=int, default=20, help='Number of dimension for POS embeddings.')
    parser.add_argument('--NER_dim', type=int, default=20, help='Number of dimension for NER embeddings.')
    parser.add_argument('--wo_left_match', default=False, help='Without left to right matching.', action='store_true')
    parser.add_argument('--wo_right_match', default=False, help='Without right to left matching', action='store_true')
    parser.add_argument('--wo_full_match', default=True, help='Without full matching.', action='store_true')
    parser.add_argument('--wo_maxpool_match', default=True, help='Without maxpooling matching', action='store_true')
    parser.add_argument('--wo_attentive_match', default=True, help='Without attentive matching', action='store_true')
    parser.add_argument('--wo_max_attentive_match', default=True, help='Without max attentive matching.',
                        action='store_true')
    parser.add_argument('--fix_word_vec', default=True, help='Fix pre-trained word embeddings during training.', action='store_true')


    #     print("CUDA_VISIBLE_DEVICES " + os.environ['CUDA_VISIBLE_DEVICES'])
    sys.stdout.flush()
    FLAGS, unparsed = parser.parse_known_args()
    tf.app.run(main=main, argv=[sys.argv[0]] + unparsed)

