from roleml.core.role.channels import Alias
from roleml.library.roles.trainer.epoch import EpochTrainer


class MyEpochTrainer(EpochTrainer):

    collect = Alias("train")
