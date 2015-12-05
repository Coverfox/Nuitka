#     Copyright 2015, Kay Hayen, mailto:kay.hayen@gmail.com
#
#     Part of "Nuitka", an optimizing Python compiler that is compatible and
#     integrates with CPython, but also works on its own.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
#
""" Code to generate and interact with compiled function objects.

"""

from nuitka.utils import Utils

from .ConstantCodes import getConstantCode
from .Contexts import PythonFunctionCoroutineContext
from .Emission import SourceCodeCollector
from .ErrorCodes import (
    getErrorExitCode,
    getErrorVariableDeclarations,
    getExceptionKeeperVariableNames,
    getExceptionPreserverVariableNames,
    getMustNotGetHereCode,
    getReleaseCode
)
from .Indentation import indented
from .LineNumberCodes import getErrorLineNumberUpdateCode
from .ModuleCodes import getModuleAccessCode
from .ParameterParsing import (
    getDirectFunctionEntryPointIdentifier,
    getParameterEntryPointIdentifier,
    getParameterParsingCode,
    getQuickEntryPointIdentifier
)
from .PythonAPICodes import getReferenceExportCode
from .templates.CodeTemplatesCoroutines import (
    template_make_coroutine_with_context_template,
    template_make_coroutine_without_context_template
)
from .templates.CodeTemplatesFrames import template_generator_initial_throw
from .templates.CodeTemplatesFunction import (
    function_dict_setup,
    function_direct_body_template,
    template_function_body,
    template_function_direct_declaration,
    template_function_exception_exit,
    template_function_make_declaration,
    template_function_return_exit,
    template_make_function_with_context_template,
    template_make_function_without_context_template
)
from .templates.CodeTemplatesGeneratorFunction import (
    template_generator_exception_exit,
    template_generator_making_with_context,
    template_generator_making_without_context,
    template_generator_noexception_exit,
    template_generator_return_exit,
    template_genfunc_function_impl_template,
    template_genfunc_generator_no_closure,
    template_genfunc_generator_no_parameters,
    template_genfunc_generator_with_own_closure,
    template_genfunc_generator_with_parameters,
    template_genfunc_generator_with_parent_closure,
    template_genfunc_yielder_body_template,
    template_genfunc_yielder_decl_template,
    template_make_genfunc_with_context_template,
    template_make_genfunc_without_context_template
)
from .TupleCodes import generateTupleCreationCode
from .VariableCodes import (
    getLocalVariableInitCode,
    getVariableCode,
    getVariableCodeName
)


def getClosureVariableProvisionCode(context, closure_variables):
    result = []

    for variable in closure_variables:
        result.append(
            getVariableCode(
                context  = context,
                variable = variable
            )
        )

    return result


def _getFunctionCreationArgs(defaults_name, kw_defaults_name,
                             annotations_name, closure_variables):
    result = []

    if defaults_name is not None:
        result.append("PyObject *defaults")

    if kw_defaults_name is not None:
        result.append("PyObject *kw_defaults")

    if annotations_name is not None:
        result.append("PyObject *annotations")

    for closure_variable in closure_variables:
        result.append(
            "PyCellObject *%s" % (
                getVariableCodeName(
                    variable   = closure_variable,
                    in_context = True
                )
            )
        )

    return result


def getFunctionMakerDecl(function_identifier, defaults_name, kw_defaults_name,
                         annotations_name, closure_variables):

    function_creation_arg_spec = _getFunctionCreationArgs(
        defaults_name     = defaults_name,
        kw_defaults_name  = kw_defaults_name,
        annotations_name  = annotations_name,
        closure_variables = closure_variables
    )

    return template_function_make_declaration % {
        "function_identifier"        : function_identifier,
        "function_creation_arg_spec" : ", ".join(
            function_creation_arg_spec
        )
    }


def getFunctionMakerCode(function_name, function_qualname, function_identifier,
                         code_identifier, parameters, closure_variables,
                         defaults_name, kw_defaults_name, annotations_name,
                         function_doc, is_generator, context):
    # We really need this many parameters here. pylint: disable=R0913

    # Functions have many details, that we express as variables
    # pylint: disable=R0914
    function_creation_args = _getFunctionCreationArgs(
        defaults_name     = defaults_name,
        kw_defaults_name  = kw_defaults_name,
        annotations_name  = annotations_name,
        closure_variables = closure_variables
    )

    if Utils.python_version < 330 or function_qualname == function_name:
        function_qualname_obj = "NULL"
    else:
        function_qualname_obj = getConstantCode(
            constant = function_qualname,
            context  = context
        )

    if closure_variables:
        context_copy = []

        closure_count = len(closure_variables)
        context_copy.append(
            "PyCellObject **closure = (PyCellObject **)malloc( %d * sizeof(PyCellObject *) );" % closure_count
        )

        for count, closure_variable in enumerate(closure_variables):
            context_copy.append(
                "closure[%d] = %s;" % (
                    count,
                    getVariableCodeName(
                        True,
                        closure_variable
                    )
                )
            )
            context_copy.append(
                "Py_INCREF( closure[%d] );" %count
            )

        if is_generator:
            template = template_make_genfunc_with_context_template
        else:
            template = template_make_function_with_context_template

        result = template % {
            "function_name_obj"          : getConstantCode(
                constant = function_name,
                context  = context
            ),
            "function_qualname_obj"      : function_qualname_obj,
            "function_identifier"        : function_identifier,
            "fparse_function_identifier" : getParameterEntryPointIdentifier(
                function_identifier = function_identifier,
            ),
            "dparse_function_identifier" : getQuickEntryPointIdentifier(
                function_identifier = function_identifier,
                parameters          = parameters
            ),
            "function_creation_args"     : ", ".join(
                function_creation_args
            ),
            "code_identifier"            : code_identifier,
            "context_copy"               : indented(context_copy),
            "function_doc"               : getConstantCode(
                constant = function_doc,
                context  = context
            ),
            "defaults"                   : "defaults"
                                             if defaults_name else
                                           "NULL",
            "kw_defaults"                : "kw_defaults"
                                             if kw_defaults_name else
                                           "NULL",
            "annotations"                : "annotations"
                                             if annotations_name else
                                           context.getConstantCode({}),
            "closure_count"              : closure_count,
            "module_identifier"          : getModuleAccessCode(
                context = context
            ),
        }
    else:
        if is_generator:
            template = template_make_genfunc_without_context_template
        else:
            template = template_make_function_without_context_template


        result = template % {
            "function_name_obj"          : getConstantCode(
                constant = function_name,
                context  = context
            ),
            "function_qualname_obj"      : function_qualname_obj,
            "function_identifier"        : function_identifier,
            "fparse_function_identifier" : getParameterEntryPointIdentifier(
                function_identifier = function_identifier,
            ),
            "dparse_function_identifier" : getQuickEntryPointIdentifier(
                function_identifier = function_identifier,
                parameters          = parameters
            ),
            "function_creation_args"     : ", ".join(
                function_creation_args
            ),
            "code_identifier"            : code_identifier,
            "function_doc"               : getConstantCode(
                constant = function_doc,
                context  = context
            ),
            "defaults"                   : "defaults"
                                             if defaults_name else
                                           "NULL",
            "kw_defaults"                : "kw_defaults"
                                             if kw_defaults_name else
                                           "NULL",
            "annotations"                : "annotations"
                                             if annotations_name else
                                           context.getConstantCode({}),
            "module_identifier"          : getModuleAccessCode(
                context = context
            ),
        }

    return result


def generateFunctionCreationCode(to_name, function_body, code_object, defaults,
                                 kw_defaults, annotations, defaults_first, emit,
                                 context):
    # This is about creating functions, which is detail ridden stuff,
    # pylint: disable=R0914
    assert function_body.needsCreation(), function_body

    def handleKwDefaults():
        if kw_defaults:
            kw_defaults_name = context.allocateTempName("kw_defaults")

            assert not kw_defaults.isExpressionConstantRef() or \
                   kw_defaults.getConstant() != {}, kw_defaults.getConstant()

            from .CodeGeneration import generateExpressionCode
            generateExpressionCode(
                to_name    = kw_defaults_name,
                expression = kw_defaults,
                emit       = emit,
                context    = context
            )
        else:
            kw_defaults_name = None

        return kw_defaults_name

    def handleDefaults():
        if defaults:
            defaults_name = context.allocateTempName("defaults")

            generateTupleCreationCode(
                to_name  = defaults_name,
                elements = defaults,
                emit     = emit,
                context  = context
            )
        else:
            defaults_name = None

        return defaults_name

    if defaults_first:
        defaults_name = handleDefaults()
        kw_defaults_name = handleKwDefaults()
    else:
        kw_defaults_name = handleKwDefaults()
        defaults_name = handleDefaults()

    if annotations:
        annotations_name = context.allocateTempName("annotations")

        from .CodeGeneration import generateExpressionCode
        generateExpressionCode(
            to_name    = annotations_name,
            expression = annotations,
            emit       = emit,
            context    = context,
        )
    else:
        annotations_name = None

    function_identifier = function_body.getCodeName()

    # Creation code needs to be done only once.
    if not context.hasHelperCode(function_identifier):
        parameters = function_body.getParameters()

        var_names = parameters.getCoArgNames()

        # Add names of local variables too.
        var_names += [
            local_variable.getName()
            for local_variable in
            function_body.getLocalVariables()
            if not local_variable.isParameterVariable()
        ]

        code_identifier = context.getCodeObjectHandle(
            filename      = function_body.getParentModule().getRunTimeFilename(),
            var_names     = code_object.getVarNames(),
            arg_count     = code_object.getArgumentCount(),
            kw_only_count = code_object.getKwOnlyParameterCount(),
            line_number   = function_body.getSourceReference().getLineNumber(),
            code_name     = function_body.getFunctionName(),
            is_generator  = function_body.isGenerator(),
            is_optimized  = not function_body.needsLocalsDict(),
            new_locals    = True,
            has_starlist  = parameters.getStarListArgumentName() is not None,
            has_stardict  = parameters.getStarDictArgumentName() is not None,
            has_closure   = function_body.getClosureVariables() != (),
            future_flags  = function_body.getSourceReference().getFutureSpec().asFlags()
        )

        maker_code = getFunctionMakerCode(
            function_name       = function_body.getFunctionName(),
            function_qualname   = function_body.getFunctionQualname(),
            function_identifier = function_identifier,
            code_identifier     = code_identifier,
            parameters          = parameters,
            closure_variables   = function_body.getClosureVariables(),
            defaults_name       = defaults_name,
            kw_defaults_name    = kw_defaults_name,
            annotations_name    = annotations_name,
            function_doc        = function_body.getDoc(),
            is_generator        = function_body.isGenerator(),
            context             = context
        )

        context.addHelperCode(function_identifier, maker_code)

        function_decl = getFunctionMakerDecl(
            function_identifier = function_body.getCodeName(),
            defaults_name       = defaults_name,
            kw_defaults_name    = kw_defaults_name,
            annotations_name    = annotations_name,
            closure_variables   = function_body.getClosureVariables()
        )

        context.addDeclaration(function_identifier, function_decl)

    getFunctionCreationCode(
        to_name             = to_name,
        function_identifier = function_body.getCodeName(),
        defaults_name       = defaults_name,
        kw_defaults_name    = kw_defaults_name,
        annotations_name    = annotations_name,
        closure_variables   = function_body.getClosureVariables(),
        emit                = emit,
        context             = context
    )

    getReleaseCode(
        release_name = annotations_name,
        emit         = emit,
        context      = context
    )


def getFunctionCreationCode(to_name, function_identifier, defaults_name,
                            kw_defaults_name, annotations_name,
                            closure_variables, emit, context):
    args = []

    if defaults_name is not None:
        args.append(getReferenceExportCode(defaults_name, context))

    if kw_defaults_name is not None:
        args.append(kw_defaults_name)

    if annotations_name is not None:
        args.append(annotations_name)

    args += getClosureVariableProvisionCode(
        context           = context,
        closure_variables = closure_variables
    )

    emit(
        "%s = MAKE_FUNCTION_%s( %s );" % (
            to_name,
            function_identifier,
            ", ".join(args)
        )
    )

    if context.needsCleanup(defaults_name):
        context.removeCleanupTempName(defaults_name)
    if context.needsCleanup(kw_defaults_name):
        context.removeCleanupTempName(kw_defaults_name)

    # No error checks, this supposedly, cannot fail.
    context.addCleanupTempName(to_name)


def getDirectFunctionCallCode(to_name, function_identifier, arg_names,
                              closure_variables, needs_check, emit, context):
    function_identifier = getDirectFunctionEntryPointIdentifier(
        function_identifier = function_identifier
    )

    suffix_args = getClosureVariableProvisionCode(
        context           = context,
        closure_variables = closure_variables
    )

    # TODO: We ought to not assume references for direct calls, or make a
    # profile if an argument needs a reference at all. Most functions don't
    # bother to release a called argument by "del" or assignment to it. We
    # could well know that ahead of time.
    for arg_name in arg_names:
        if context.needsCleanup(arg_name):
            context.removeCleanupTempName(arg_name)
        else:
            emit("Py_INCREF( %s );" % arg_name)

    emit(
        "%s = %s( %s );" % (
            to_name,
            function_identifier,
            ", ".join(
                arg_names + suffix_args
            )
        )
    )

    # Arguments are owned to the called in direct function call.
    for arg_name in arg_names:
        if context.needsCleanup(arg_name):
            context.removeCleanupTempName(arg_name)

    getErrorExitCode(
        check_name  = to_name,
        emit        = emit,
        needs_check = needs_check,
        context     = context
    )

    context.addCleanupTempName(to_name)


def getFunctionDirectClosureArgs(closure_variables):
    result = []

    for closure_variable in closure_variables:
        if closure_variable.isSharedTechnically():
            result.append(
                "PyCellObject *%s" % (
                    getVariableCodeName(
                        in_context = True,
                        variable   = closure_variable
                    )
                )
            )
        else:
            # TODO: The reference is only needed for Python3, could make it
            # version dependent.
            result.append(
                "PyObject *&%s" % (
                    getVariableCodeName(
                        in_context = True,
                        variable   = closure_variable
                    )
                )
            )

    return result


def getFunctionDirectDecl(function_identifier, closure_variables,
                          parameter_variables, file_scope):

    parameter_objects_decl = [
        "PyObject *_python_par_" + variable.getCodeName()
        for variable in
        parameter_variables
    ]

    parameter_objects_decl += getFunctionDirectClosureArgs(closure_variables)

    result = template_function_direct_declaration % {
        "file_scope"           : file_scope,
        "function_identifier"  : function_identifier,
        "direct_call_arg_spec" : ", ".join(parameter_objects_decl),
    }

    return result


def getFunctionCode(context, function_name, function_identifier, parameters,
                    closure_variables, user_variables, temp_variables,
                    function_codes, function_doc, file_scope,
                    needs_exception_exit):

    # Many arguments, as we need much input transferred, pylint: disable=R0913

    # Functions have many details, that we express as variables, with many
    # branches to decide, pylint: disable=R0912,R0914

    parameter_variables, entry_point_code, parameter_objects_decl = \
      getParameterParsingCode(
        function_identifier = function_identifier,
        function_name       = function_name,
        parameters          = parameters,
        needs_creation      = context.isForCreatedFunction(),
        context             = context,
    )

    function_parameter_decl = [
        getLocalVariableInitCode(
            variable  = variable,
            init_from = "_python_par_" + variable.getCodeName()
        )
        for variable in
        parameter_variables
    ]


    # User local variable initializations
    local_var_inits = [
        getLocalVariableInitCode(
            variable = variable,
        )
        for variable in
        user_variables + tuple(
            variable
            for variable in
            temp_variables
        )
    ]

    if context.needsExceptionVariables():
        local_var_inits.extend(getErrorVariableDeclarations())

    for keeper_index in range(1, context.getKeeperVariableCount()+1):
        local_var_inits.extend(getExceptionKeeperVariableNames(keeper_index))

    for preserver_id in context.getExceptionPreserverCounts():
        local_var_inits.extend(getExceptionPreserverVariableNames(preserver_id))

    local_var_inits += [
        "%s%s%s;" % (
            tmp_type,
            ' ' if not tmp_type.endswith('*') else "",
            tmp_name
        )
        for tmp_name, tmp_type in
        context.getTempNameInfos()
    ]

    local_var_inits += context.getFrameDeclarations()

    # TODO: Could avoid this unless try/except or try/finally with returns
    # occur.
    if context.hasTempName("return_value"):
        local_var_inits.append("tmp_return_value = NULL;")
    for tmp_name, tmp_type in context.getTempNameInfos():
        if tmp_name.startswith("tmp_outline_return_value_"):
            local_var_inits.append("%s = NULL;" % tmp_name)

    function_doc = getConstantCode(
        context  = context,
        constant = function_doc
    )

    function_locals = []

    if context.hasLocalsDict():
        function_locals += function_dict_setup.split('\n')
        function_cleanup = "Py_DECREF( locals_dict );\n"
    else:
        function_cleanup = ""

    function_locals += function_parameter_decl + local_var_inits

    result = ""

    emit = SourceCodeCollector()

    getMustNotGetHereCode(
        reason  = "Return statement must have exited already.",
        context = context,
        emit    = emit
    )

    function_exit = indented(emit.codes) + "\n\n"
    del emit

    if needs_exception_exit:
        function_exit += template_function_exception_exit % {
            "function_cleanup"    : function_cleanup,
        }

    if context.hasTempName("return_value"):
        function_exit += indented(
            template_function_return_exit % {
                "function_cleanup" : indented(function_cleanup),
            }
        )

    if context.isForDirectCall():
        parameter_objects_decl += getFunctionDirectClosureArgs(closure_variables)

        result += function_direct_body_template % {
            "file_scope"                   : file_scope,
            "function_identifier"          : function_identifier,
            "direct_call_arg_spec"         : ", ".join(
                parameter_objects_decl
            ),
            "function_locals"              : indented(function_locals),
            "function_body"                : indented(function_codes),
            "function_exit"                : function_exit
        }
    else:
        result += template_function_body % {
            "function_identifier"          : function_identifier,
            "parameter_objects_decl"       : ", ".join(parameter_objects_decl),
            "function_locals"              : indented(function_locals),
            "function_body"                : indented(function_codes),
            "function_exit"                : function_exit
        }

    if context.isForCreatedFunction():
        result += entry_point_code

    return result


def getGeneratorFunctionCode(context, function_name, function_qualname,
                             function_identifier, code_identifier, parameters,
                             closure_variables, user_variables, temp_variables,
                             function_codes, function_doc, needs_exception_exit,
                             needs_generator_return):
    # We really need this many parameters here. pylint: disable=R0913

    # Functions have many details, that we express as variables, with many
    # branches to decide, pylint: disable=R0912,R0914,R0915

    # Parameter parsing code of the function. TODO: Somehow we duplicate a lot
    # of what a function is for these. We should make these generator object
    # creations explicit, so they can be in-lined, and the duplication of some
    # of this code could be avoided.
    parameter_variables, entry_point_code, parameter_objects_decl = \
      getParameterParsingCode(
        function_identifier = function_identifier,
        function_name       = function_name,
        parameters          = parameters,
        needs_creation      = context.isForCreatedFunction(),
        context             = context,
    )

    # For direct calls, append the closure variables to the argument list.
    if context.isForDirectCall():
        for count, variable in enumerate(closure_variables):
            parameter_objects_decl.append(
                "PyCellObject *%s" % (
                    getVariableCodeName(
                        in_context = True,
                        variable   = variable
                    )
                )
            )

    function_locals = []
    for user_variable in user_variables + temp_variables:
        function_locals.append(
            getLocalVariableInitCode(
                variable = user_variable,
            )
        )

    function_doc = getConstantCode(
        context  = context,
        constant = function_doc
    )

    if context.hasLocalsDict():
        function_locals += function_dict_setup.split('\n')

    if context.needsExceptionVariables():
        function_locals.extend(getErrorVariableDeclarations())

    for keeper_index in range(1, context.getKeeperVariableCount()+1):
        function_locals.extend(getExceptionKeeperVariableNames(keeper_index))

    for preserver_id in context.getExceptionPreserverCounts():
        function_locals.extend(getExceptionPreserverVariableNames(preserver_id))

    function_locals += [
        "%s%s%s;" % (
            tmp_type,
            ' ' if not tmp_type.endswith('*') else "",
            tmp_name
        )
        for tmp_name, tmp_type in
        context.getTempNameInfos()
    ]

    function_locals += context.getFrameDeclarations()

    # TODO: Could avoid this unless try/except or try/finally with returns
    # occur.
    if context.hasTempName("generator_return"):
        function_locals.append("tmp_generator_return = false;")
    if context.hasTempName("return_value"):
        function_locals.append("tmp_return_value = NULL;")
    for tmp_name, tmp_type in context.getTempNameInfos():
        if tmp_name.startswith("tmp_outline_return_value_"):
            function_locals.append("%s = NULL;" % tmp_name)


    if needs_exception_exit:
        generator_exit = template_generator_exception_exit % {}
    else:
        generator_exit = template_generator_noexception_exit % {}

    if needs_generator_return:
        generator_exit += template_generator_return_exit % {}

    result = template_genfunc_yielder_body_template % {
        "function_identifier" : function_identifier,
        "function_body"       : indented(function_codes),
        "function_var_inits"  : indented(function_locals),
        "generator_exit"      : generator_exit
    }

    # Code to copy parameters into a "PyObject **" array, attaching it to the
    # generator object to be created in the cause of the function call.
    parameter_count = len(parameter_variables)

    # Prepare declaration of parameters array to the generator object creation.
    if parameter_count > 0:
        parameter_copy = []

        for count, variable in enumerate(parameter_variables):
            if variable.isSharedTechnically():
                parameter_copy.append(
                    "parameters[%d] = (PyObject *)PyCell_NEW1( _python_par_%s );" % (
                        count,
                        variable.getCodeName()
                    )
                )
            else:
                parameter_copy.append(
                    "parameters[%d] = _python_par_%s;" % (
                        count,
                        variable.getCodeName()
                    )
                )

        parameters_decl = template_genfunc_generator_with_parameters  % {
            "parameter_copy"      : indented(parameter_copy),
            "parameter_count"     : parameter_count
        }
    else:
        parameters_decl = template_genfunc_generator_no_parameters  % {}

    # Prepare declaration of parameters array to the generator object creation.
    closure_count = len(closure_variables)

    if closure_count > 0:
        if context.isForDirectCall():
            closure_copy = []

            for count, variable in enumerate(closure_variables):
                closure_copy.append(
                    "closure[%d] = %s;" % (
                        count,
                        getVariableCodeName(
                            in_context = True,
                            variable   = variable
                        )
                    )
                )
                closure_copy.append(
                    "Py_INCREF( closure[%d] );" % count
                )


            closure_decl = template_genfunc_generator_with_own_closure % {
                "closure_copy" : '\n'.join(closure_copy),
                "closure_count" : closure_count
            }
        else:
            closure_decl = template_genfunc_generator_with_parent_closure % {
                "closure_count" : closure_count
            }
    else:
        closure_decl = template_genfunc_generator_no_closure % {}

    if Utils.python_version < 350 or context.isForDirectCall():
        function_name_obj = getConstantCode(context, function_name)
    else:
        function_name_obj = "self->m_name"

    if Utils.python_version < 350:
        function_qualname_obj = "NULL"
    elif context.isForDirectCall():
        function_qualname_obj = getConstantCode(context, function_qualname)
    else:
        function_qualname_obj = "self->m_qualname"

    result += template_genfunc_function_impl_template % {
        "function_name"          : function_name,
        "function_name_obj"      : function_name_obj,
        "function_qualname_obj"  : function_qualname_obj,
        "function_identifier"    : function_identifier,
        "code_identifier"        : code_identifier,
        "parameter_decl"         : parameters_decl,
        "parameter_count"        : parameter_count,
        "closure_decl"           : closure_decl,
        "closure_count"          : closure_count,
        "parameter_objects_decl" : ", ".join(parameter_objects_decl),
    }

    if context.isForCreatedFunction():
        result += entry_point_code

    return result


def getGeneratorObjectCode(context, function_identifier, user_variables,
                           temp_variables, function_codes, needs_exception_exit,
                           needs_generator_return):
    function_locals = []

    for user_variable in user_variables + temp_variables:
        function_locals.append(
            getLocalVariableInitCode(
                variable = user_variable,
            )
        )

    if context.hasLocalsDict():
        function_locals += function_dict_setup.split('\n')

    if context.needsExceptionVariables():
        function_locals.extend(getErrorVariableDeclarations())

    for keeper_index in range(1, context.getKeeperVariableCount()+1):
        function_locals.extend(getExceptionKeeperVariableNames(keeper_index))

    for preserver_id in context.getExceptionPreserverCounts():
        function_locals.extend(getExceptionPreserverVariableNames(preserver_id))

    function_locals += [
        "%s%s%s;" % (
            tmp_type,
            ' ' if not tmp_type.endswith('*') else "",
            tmp_name
        )
        for tmp_name, tmp_type in
        context.getTempNameInfos()
    ]

    function_locals += context.getFrameDeclarations()

    # TODO: Could avoid this unless try/except or try/finally with returns
    # occur.
    if context.hasTempName("generator_return"):
        function_locals.append("tmp_generator_return = false;")
    if context.hasTempName("return_value"):
        function_locals.append("tmp_return_value = NULL;")
    for tmp_name, tmp_type in context.getTempNameInfos():
        if tmp_name.startswith("tmp_outline_return_value_"):
            function_locals.append("%s = NULL;" % tmp_name)


    if needs_exception_exit:
        generator_exit = template_generator_exception_exit % {}
    else:
        generator_exit = template_generator_noexception_exit % {}

    if needs_generator_return:
        generator_exit += template_generator_return_exit % {}

    result = template_genfunc_yielder_body_template % {
        "function_identifier" : function_identifier,
        "function_body"       : indented(function_codes),
        "function_var_inits"  : indented(function_locals),
        "generator_exit"      : generator_exit
    }

    return result


def generateCoroutineCreationCode(to_name, expression, emit, context):
    coroutine_body = expression.getCoroutineBody()
    closure_variables = coroutine_body.getClosureVariables()

    code_identifier = coroutine_body.getCodeName()

    function_codes = SourceCodeCollector()

    coroutine_context = PythonFunctionCoroutineContext(
        parent   = context,
        function = coroutine_body
    )

    # TODO: Should come from registry instead.
    from .CodeGeneration import generateStatementSequenceCode

    generateStatementSequenceCode(
        statement_sequence = coroutine_body.getBody(),
        emit               = function_codes,
        context            = coroutine_context
    )

    if closure_variables:
        emit(
            template_make_coroutine_with_context_template % {
                "to_name"         : to_name,
                "code_identifier" : code_identifier
            }
        )
    else:
        emit(
            template_make_coroutine_without_context_template % {
                "to_name"         : to_name,
                "code_identifier" : code_identifier
            }
        )


def generateMakeGeneratorObjectCode(to_name, expression, emit, context):
    generator_object_body = expression.getGeneratorRef().getFunctionBody()

    closure_variables = generator_object_body.getClosureVariables()

    generator_name = generator_object_body.getFunctionName()
    generator_qualname = generator_object_body.getFunctionQualname()

    generator_name_obj = getConstantCode(
        constant = generator_name,
        context  = context
    )

    if Utils.python_version < 330 or generator_qualname == generator_name:
        generator_qualname_obj = "NULL"
    else:
        generator_qualname_obj = getConstantCode(
            constant = generator_qualname,
            context  = context
        )

    code_object = expression.getCodeObject()

    code_identifier = context.getCodeObjectHandle(
        filename      = generator_object_body.getParentModule().getRunTimeFilename(),
        var_names     = code_object.getVarNames(),
        arg_count     = code_object.getArgumentCount(),
        kw_only_count = code_object.getKwOnlyParameterCount(),
        line_number   = generator_object_body.getSourceReference().getLineNumber(),
        code_name     = code_object.getCodeObjectName(),
        is_generator  = True,
        is_optimized  = True,
        new_locals    = not generator_object_body.needsLocalsDict(),
        has_starlist  = False,
        has_stardict  = False,
        has_closure   = len(closure_variables) > 0,
        future_flags  = generator_object_body.getSourceReference().getFutureSpec().asFlags()
    )

    if closure_variables:
        closure_copy = []

        for count, variable in enumerate(closure_variables):
            closure_copy.append(
                "closure[%d] = %s;" % (
                    count,
                    getVariableCode(
                        context  = context,
                        variable = variable
                    )
                )
            )
            closure_copy.append(
                "Py_INCREF( closure[%d] );" % count
            )

        closure_making = template_genfunc_generator_with_own_closure % {
            "closure_copy" : indented(closure_copy),
            "closure_count" : len(closure_variables)
        }


        emit(
            template_generator_making_with_context % {
                "closure_making"         : closure_making,
                "to_name"                : to_name,
                "generator_identifier"   : generator_object_body.getCodeName(),
                "generator_name_obj"     : generator_name_obj,
                "generator_qualname_obj" : generator_qualname_obj,
                "code_identifier"        : code_identifier,
                "closure_count"          : len(closure_variables)
            }
        )
    else:
        emit(
            template_generator_making_without_context % {
                "to_name"                : to_name,
                "generator_identifier"   : generator_object_body.getCodeName(),
                "generator_name_obj"     : generator_name_obj,
                "generator_qualname_obj" : generator_qualname_obj,
                "code_identifier"        : code_identifier
            }
        )

    context.addCleanupTempName(to_name)


def getExportScopeCode(cross_module):
    if cross_module:
        return "NUITKA_CROSS_MODULE"
    else:
        return "NUITKA_LOCAL_MODULE"


def generateGeneratorEntryCode(statement, emit, context):
    context.setCurrentSourceCodeReference(statement.getSourceReference())

    emit(
        template_generator_initial_throw % {
            "frame_exception_exit"  : context.getExceptionEscape(),
            "set_error_line_number" : getErrorLineNumberUpdateCode(context)
        }
    )

def generateFunctionDeclCode(function_body):
    if function_body.isExpressionGeneratorObjectBody():
        return template_genfunc_yielder_decl_template % {
            "function_identifier" : function_body.getCodeName(),
        }
    elif function_body.needsDirectCall():
        return getFunctionDirectDecl(
            function_identifier = function_body.getCodeName(),
            closure_variables   = function_body.getClosureVariables(),
            parameter_variables = function_body.getParameters().getAllVariables(),
            file_scope          = getExportScopeCode(
                cross_module = function_body.isCrossModuleUsed()
            )
        )
    else:
        return None
