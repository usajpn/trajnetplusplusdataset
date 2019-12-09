"""Create Trajnet data from original datasets."""
import argparse
import pysparkling
import scipy.io

from . import readers
from .scene import Scenes
from .get_type import trajectory_type
from .get_test_type import trajectory_test_type


def biwi(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .textFile(input_file)
            .map(readers.biwi)
            .cache())


def crowds(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .wholeTextFiles(input_file)
            .values()
            .flatMap(readers.crowds)
            .cache())


def mot(sc, input_file):
    """Was 7 frames per second in original recording."""
    print('processing ' + input_file)
    return (sc
            .textFile(input_file)
            .map(readers.mot)
            .filter(lambda r: r.frame % 2 == 0)
            .cache())


def edinburgh(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .wholeTextFiles(input_file)
            .zipWithIndex()
            .flatMap(readers.edinburgh)
            .cache())


def syi(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .wholeTextFiles(input_file)
            .flatMap(readers.syi)
            .cache())


def dukemtmc(sc, input_file):
    print('processing ' + input_file)
    contents = scipy.io.loadmat(input_file)['trainData']
    return (sc
            .parallelize(readers.dukemtmc(contents))
            .cache())


def wildtrack(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .wholeTextFiles(input_file)
            .flatMap(readers.wildtrack)
            .cache())

def cff(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .textFile(input_file)
            .map(readers.cff)
            .filter(lambda r: r is not None)
            .cache())

def lcas(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .textFile(input_file)
            .map(readers.lcas)
            .cache())

def controlled(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .textFile(input_file)
            .map(readers.controlled)
            .cache())

def get_trackrows(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .textFile(input_file)
            .map(readers.get_trackrows)
            .filter(lambda r: r is not None)
            .cache())

# def write(input_rows, output_file, train_fraction=0.6, val_fraction=0.2, fps=2.5, order_frames=False):
def write(input_rows, output_file, args):
    """ Write Valid Scenes without categorization """

    print(" Entering Writing ")
    ## To handle two different time stamps 7:00 and 17:00 of cff
    if args.order_frames:
        frames = sorted(set(input_rows.map(lambda r: r.frame).toLocalIterator()),
                        key=lambda frame: frame % 100000)
    else:
        frames = sorted(set(input_rows.map(lambda r: r.frame).toLocalIterator()))
    
    # split
    train_split_index = int(len(frames) * args.train_fraction)
    val_split_index = train_split_index + int(len(frames) * args.val_fraction)
    train_frames = set(frames[:train_split_index])
    val_frames = set(frames[train_split_index:val_split_index])
    test_frames = set(frames[val_split_index:])

    # train dataset
    train_rows = input_rows.filter(lambda r: r.frame in train_frames)
    train_output = output_file.format(split='train')
    train_scenes = Scenes(fps=args.fps, start_scene_id=0, args=args).rows_to_file(train_rows, train_output)

    # validation dataset
    val_rows = input_rows.filter(lambda r: r.frame in val_frames)
    val_output = output_file.format(split='val')
    val_scenes = Scenes(fps=args.fps, start_scene_id=train_scenes.scene_id, args=args).rows_to_file(val_rows, val_output)

    # public test dataset
    test_rows = input_rows.filter(lambda r: r.frame in test_frames)
    test_output = output_file.format(split='test')
    test_scenes = Scenes(fps=args.fps, start_scene_id=val_scenes.scene_id, args=args) # !!! Chunk Stride
    test_scenes.rows_to_file(test_rows, test_output)

    # private test dataset
    private_test_output = output_file.format(split='test_private')
    private_test_scenes = Scenes(fps=args.fps, start_scene_id=val_scenes.scene_id, args=args)
    private_test_scenes.rows_to_file(test_rows, private_test_output)

def categorize(sc, input_file, args):
    """ Categorize the Scenes """

    print(" Entering Categorizing ")

    # Decide which folders to categorize #
    if args.train_fraction == 1.0:
        #Train
        print("Only train")
        train_rows = get_trackrows(sc, input_file.replace('split', '').format('train'))
        train_id = trajectory_type(train_rows, input_file.replace('split', '').format('train'),
                                   fps=args.fps, track_id=0, args=args)

    elif (args.train_fraction + args.val_fraction) == 0.0:
        #Test
        print("Only test")
        test_rows = get_trackrows(sc, input_file.replace('split', '').format('test_private'))
        _ = trajectory_test_type(test_rows, input_file.replace('split', '').format('test_private'),
                            fps=args.fps, track_id=0, args=args)

    else:
        print("All Three")
        #Train
        train_rows = get_trackrows(sc, input_file.replace('split', '').format('train'))
        train_id = trajectory_type(train_rows, input_file.replace('split', '').format('train'),
                                   fps=args.fps, track_id=0, args=args)

        #Val
        val_rows = get_trackrows(sc, input_file.replace('split', '').format('val'))
        val_id = trajectory_type(val_rows, input_file.replace('split', '').format('val'),
                                 fps=args.fps, track_id=train_id, args=args)

        #Test
        test_rows = get_trackrows(sc, input_file.replace('split', '').format('test_private'))
        _ = trajectory_test_type(test_rows, input_file.replace('split', '').format('test_private'),
                            fps=args.fps, track_id=val_id, args=args)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obs_len', type=int, default=9,
                        help='Length of observation')
    parser.add_argument('--pred_len', type=int, default=12,
                        help='Length of prediction')
    parser.add_argument('--train_fraction', default=0.6, type=float,
                        help='Training set fraction')
    parser.add_argument('--val_fraction', default=0.2, type=float,
                        help='Validation set fraction')
    parser.add_argument('--fps', default=2.5, type=float,
                        help='fps')    
    parser.add_argument('--order_frames', action='store_true',
                        help='For CFF')
    parser.add_argument('--chunk_stride', type=int, default=2,
                        help='Sampling Stride')
    parser.add_argument('--min_length', default=0.0, type=float,
                        help='Min Length of Primary Trajectory')
    parser.add_argument('--acceptance', nargs='+', type=float,
                        default=[0.1, 1, 1, 1],
                        help='acceptance ratio of different trajectory types')

    args = parser.parse_args()
    sc = pysparkling.Context()

    # Example Conversions
    # # real datasets
    write(biwi(sc, 'data/raw/biwi/seq_hotel/obsmat.txt'),
          'output_pre/{split}/biwi_hotel.ndjson', args)
    categorize(sc, 'output_pre/{split}/biwi_hotel.ndjson', args)
    write(crowds(sc, 'data/raw/crowds/crowds_zara01.vsp'),
          'output_pre/{split}/crowds_zara01.ndjson', args)
    categorize(sc, 'output_pre/{split}/crowds_zara01.ndjson', args)
    write(crowds(sc, 'data/raw/crowds/crowds_zara03.vsp'),
          'output_pre/{split}/crowds_zara03.ndjson', args)
    categorize(sc, 'output_pre/{split}/crowds_zara03.ndjson', args)
    write(crowds(sc, 'data/raw/crowds/students001.vsp'),
          'output_pre/{split}/crowds_students001.ndjson', args)
    categorize(sc, 'output_pre/{split}/crowds_students001.ndjson', args)
    write(crowds(sc, 'data/raw/crowds/students003.vsp'),
          'output_pre/{split}/crowds_students003.ndjson', args)
    categorize(sc, 'output_pre/{split}/crowds_students003.ndjson', args)

    # # # new datasets
    write(lcas(sc, 'data/raw/lcas/test/data.csv'),
          'output_pre/{split}/lcas.ndjson', args)
    categorize(sc, 'output_pre/{split}/lcas.ndjson', args)

    args.fps = 2
    write(wildtrack(sc, 'data/raw/wildtrack/Wildtrack_dataset/annotations_positions/*.json'),
          'output_pre/{split}/wildtrack.ndjson', args)
    categorize(sc, 'output_pre/{split}/wildtrack.ndjson', args)

    # # CFF: More trajectories
    # # Chunk_stride > 20 preferred.
    # write(cff(sc, 'data/raw/cff_dataset/al_position2013-02-10.csv'),
    #       'output_pre/{split}/cff_10.ndjson', order_frames=True)
    # categorize(sc, 'output_pre/{split}/cff_10.ndjson')
    # write(cff(sc, 'data/raw/cff_dataset/al_position2013-02-06.csv'),
    #       'output_pre/{split}/cff_06.ndjson', order_frames=True)
    # categorize(sc, 'output_pre/{split}/cff_06.ndjson')


    # Eg. of 'Train Only' categorization
    # write(biwi(sc, 'data/raw/biwi/seq_hotel/obsmat.txt'),
    #       'output_pre/{split}/biwi_hotel.ndjson', train_fraction=1.0, val_fraction=0)
    # categorize(sc, 'output_pre/{split}/biwi_hotel.ndjson', train=True)

    # Eg. of 'Test Only' categorization
    # write(biwi(sc, 'data/raw/biwi/seq_hotel/obsmat.txt'),
    #       'output_pre/{split}/biwi_hotel.ndjson', train_fraction=0.0, val_fraction=0)
    # categorize(sc, 'output_pre/{split}/biwi_hotel.ndjson', test=True)

    # CA
    # Generate Trajectories First. #
    # # Train
    # write(controlled(sc, 'data/raw/controlled/orca_traj_close.txt'),
    #       'output_pre/{split}/controlled_close.ndjson', train_fraction=1.0, val_fraction=0)
    # categorize(sc, 'output_pre/{split}/controlled_close.ndjson', train=True)
    # write(controlled(sc, 'data/raw/controlled/orca_traj_medium1.txt'),
    #       'output_pre/{split}/controlled_medium1.ndjson', train_fraction=1.0, val_fraction=0)
    # categorize(sc, 'output_pre/{split}/controlled_medium1.ndjson', train=True)
    # write(controlled(sc, 'data/raw/controlled/orca_traj_medium2.txt'),
    #       'output_pre/{split}/controlled_medium2.ndjson', train_fraction=1.0, val_fraction=0)
    # categorize(sc, 'output_pre/{split}/controlled_medium2.ndjson', train=True)
    # write(controlled(sc, 'data/raw/controlled/orca_traj_far.txt'),
    #       'output_pre/{split}/controlled_far.ndjson', train_fraction=1.0, val_fraction=0)
    # categorize(sc, 'output_pre/{split}/controlled_far.ndjson', train=True)
    # write(controlled(sc, 'data/raw/controlled/circle_orca_traj_4.txt'),
    #       'output_pre/{split}/controlled_4.ndjson')
    # categorize(sc, 'output_pre/{split}/controlled_4.ndjson')
    # write(controlled(sc, 'data/raw/controlled/circle_orca_traj_6.txt'),
    #       'output_pre/{split}/controlled_6.ndjson', train_fraction=1.0, val_fraction=0)
    # categorize(sc, 'output_pre/{split}/controlled_6.ndjson', train=True)

if __name__ == '__main__':
    main()
