from ANN_simulation import *
import argparse, subprocess, os

parser = argparse.ArgumentParser()
parser.add_argument("mol_type", type=str, help="molecule type of the pdb files")
parser.add_argument("--path", type=str, default="../target", help="specify the directory/file containing the pdb files")
parser.add_argument("--step_interval", type=int, default=1, help="step interval")
args = parser.parse_args()

molecule_type = Sutils.create_subclass_instance_using_name(args.mol_type)
temp_path = args.path

if os.path.exists(temp_path):
    molecule_type.generate_coordinates_from_pdb_files(path_for_pdb=temp_path, step_interval=args.step_interval)
else:
    print "%s not existed!" % temp_path
