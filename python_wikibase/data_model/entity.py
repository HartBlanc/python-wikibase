from copy import deepcopy

from wikibase_api import ApiError

from python_wikibase.utils.data_types import class_to_data_type, data_type_to_class
from python_wikibase.utils.exceptions import EditError, NotFoundError, SearchError
from python_wikibase.value import Value


class Entity(Value):
    def __init__(self, py_wb, api, language, entity_type):
        """Wikibase entity (item or property)

        :param py_wb: PyWikibase API wrapper object
        :type py_wb: Wikibase
        :param language: Language for searches and edits on Wikibase
        :type language: str
        :param entity_type: One of ["item", "property"]
        :type entity_type: str
        """
        self.entity_type = entity_type
        self.entity_id = None
        self.label = None
        self.description = None
        self.aliases = None
        self.claims = None
        self.data_type = None  # Only applies to Property

        super().__init__(py_wb, api, language)

    def marshal(self):
        return {"entity-type": self.entity_type, "numeric-id": int(self.entity_id[1:])}

    def _create(self, content):
        """Create a new entity with the specified label and content

        :param content: Content of the new entity
        :type content: dict
        :return: self
        :rtype: Entity
        """
        # Create entity
        try:
            r = self.api.entity.add(self.entity_type, content)
        except ApiError as e:
            raise EditError(f"Could not create {self.entity_type}: {e}") from None
        entity = r["entity"]

        # Save entity_id and label
        self.entity_id = entity["id"]
        self.label = self.py_wb.Label().unmarshal(self.entity_id, entity["labels"])

        # Save empty attributes
        self.description = self.py_wb.Description().unmarshal(self.entity_id, {})
        self.aliases = self.py_wb.Aliases().unmarshal(self.entity_id, {})
        self.claims = self.py_wb.Claims().unmarshal(self.entity_id, {})

        return self

    def get(self, entity_ids=None, attributes=None):
        """Fetch information about the specified entity from Wikibase

        :param entity_ids: IDs of the entity on Wikibase (e.g. ["Q1", "Q2"])
        :type entity_id: Optional[list[str]]
        :param attributes: The attributes to fetch for the entities
        :type attributes: Optional[list[str]]
        :return: requested entities
        :rtype: list[Entity]
        """
        if not entity_ids:
            if not self.entity_id:
                raise ValueError(
                    f"You need to specify the {self.entity_type}'s entity_id before being able to "
                    f"use the get() function"
                )
            else:
                entity_ids = [self.entity_id]

        try:
            r = self.api.entity.get(entity_ids, attributes=attributes)
        except ApiError as e:
            raise SearchError(f"Could not get {self.entity_type}: {e}") from None
        if "success" not in r or r["success"] != 1:
            raise SearchError(f"Unsuccessful response for {self.entity_type}: {r}") from None

        entities = []
        for entity_id, entity in r["entities"].items():
            if "missing" in entity:
                raise NotFoundError(
                    f'No {self.entity_type} found with the entity_id "{entity_id}"'
                )

            if self.entity_id == entity_id:
                e = self
            else:
                e = deepcopy(self)
            e.entity_id = entity["id"]
            if "lables" in entity:
                e.label = e.py_wb.Label().unmarshal(e.entity_id, entity["labels"])

            # Save data_type
            if e.entity_type == "property":
                if "datatype" in entity:
                    e.data_type = data_type_to_class[entity["datatype"]]

            # Save other attributes
            if "descriptions" in entity:
                e.description = e.py_wb.Description().unmarshal(
                    e.entity_id, entity["descriptions"]
                )
            if "aliases" in entity:
                e.aliases = self.py_wb.Aliases().unmarshal(e.entity_id, entity["aliases"])
            if "claims" in entity:
                e.claims = self.py_wb.Claims().unmarshal(e.entity_id, entity["claims"])
            entities.append(e)

        return entities

    def delete(self):
        """Delete the entity from Wikibase"""
        if self.entity_type == "item":
            title = "Item:" + self.entity_id
        else:
            title = "Property:" + self.entity_id
        try:
            self.api.entity.remove(title)
        except ApiError as e:
            raise EditError(f"Could not delete {self.entity_type}: {e}") from None


class Item(Entity):
    def __init__(self, py_wb, wb, language):
        super().__init__(py_wb, wb, language, "item")

    def create(self, label):
        content = {"labels": {self.language: {"language": self.language, "value": label}}}
        return super()._create(content)


class Property(Entity):
    def __init__(self, py_wb, wb, language):
        super().__init__(py_wb, wb, language, "property")

    def create(self, label, data_type="StringValue"):
        if data_type not in class_to_data_type.keys():
            raise ValueError(
                f'"{data_type}" is not a valid value for data_type, must be one of must be one of '
                f"{class_to_data_type.keys()}"
            )
        self.data_type = data_type
        content = {
            "labels": {self.language: {"language": self.language, "value": label}},
            "datatype": class_to_data_type[data_type],
        }
        return super()._create(content)


def check_item_param(prop, param_name="item"):
    if not isinstance(prop, Item):
        raise ValueError(f"{param_name} parameter must be instance of Item class")


def check_prop_param(prop, param_name="property"):
    if not isinstance(prop, Property):
        raise ValueError(f"{param_name} parameter must be instance of Property class")
